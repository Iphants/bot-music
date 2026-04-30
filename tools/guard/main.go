package main

import (
	"bufio"
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"time"
)

const iterasi = 500000

type CatatanFile struct {
	Path   string
	Size   int64
	SHA256 string
}

type SnapshootData struct {
	Version   int           `json:"version"`
	CreatedAt string        `json:"created_at"`
	SaltB64   string        `json:"salt_b64"`
	Signature string        `json:"signature"`
	Files     []CatatanFile `json:"files"`
}

type RuntimeConfig struct {
	Version        int    `json:"version"`
	CreatedAt      string `json:"created_at"`
	TokenSaltB64   string `json:"token_salt_b64"`
	TokenNonceB64  string `json:"token_nonce_b64"`
	TokenCipherB64 string `json:"token_cipher_b64"`
	MusicDir       string `json:"music_dir"`
}

func inp(prompt string) string {
	fmt.Print(prompt)
	reader := bufio.NewReader(os.Stdin)
	text, err := reader.ReadString('\n')
	if err != nil {
		return ""
	}
	return strings.TrimSpace(text)
}

func inpkosong(prompt string) string {
	if runtime.GOOS == "windows" {
		return inpkosongWindows(prompt)
	}
	return inpkosongUnix(prompt)
}

func inpkosongUnix(prompt string) string {
	fmt.Print(prompt)
	disable := exec.Command("stty", "-echo")
	disable.Stdin = os.Stdin

	if err := disable.Run(); err != nil {
		fmt.Println()
		fmt.Println("[WARN] gagal matiin echo terminal, input akan keliatan")
		return inp("")
	}
	defer func() {
		enable := exec.Command("stty", "echo")
		enable.Stdin = os.Stdin
		_ = enable.Run()
		fmt.Println()
	}()
	reader := bufio.NewReader(os.Stdin)
	text, err := reader.ReadString('\n')
	if err != nil {
		return ""
	}
	return strings.TrimSpace(text)
}

func inpkosongWindows(prompt string) string {
	script := fmt.Sprintf(`
	$p = Read-Host -Prompt %q -AsSecureString
	$b = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($p)
	try {
		[Runtime.InteropServices.Marshal]::PtrToStringBSTR($b)
	} finally {
	[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($b)
	}`, prompt)
	cmd := exec.Command("powershell", "-NoProfile", "-Command", script)
	out, err := cmd.Output()
	if err != nil {
		fmt.Println("[WARN] gagal make PowerShell secure input, input akan keliatan")
		return inp(prompt)
	}
	return strings.TrimSpace(string(out))
}

func fileAda(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return !info.IsDir()
}

func folderAda(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}
	return info.IsDir()
}

func cariRootProject() (string, error) {
	dir, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		mainPy := filepath.Join(dir, "main.py")
		appDir := filepath.Join(dir, "app")

		if fileAda(mainPy) && folderAda(appDir) {
			return dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return "", fmt.Errorf("root project ga ketemu, jalanin guard dari dalem project")
}

func pathRel(root string, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil {
		return path
	}
	return filepath.ToSlash(rel)
}

func dataDir(root string) string {
	return filepath.Join(root, "app", "data")
}

func snapshootPath(root string) string {
	return filepath.Join(dataDir(root), "workspace_snapshoot.json")
}

func confgPath(root string) string {
	return filepath.Join(dataDir(root), "runtime_config.json")
}

func Skip(rel string) bool {
	rel = filepath.ToSlash(rel)
	skipDirsNames := map[string]bool{
		".git": true, ".venv": true, "venv": true, "__pycache__": true, "node_modules": true, ".pytest_cache": true, ".mypy_cache": true, "bot-env": true,
	}

	parts := strings.Split(rel, "/")
	for _, part := range parts {
		if skipDirsNames[part] {
			return true
		}
	}
	if rel == "app/data" || strings.HasPrefix(rel, "app/data/") {
		return true
	}
	skipSuffix := []string{
		".pyc", ".pyo", ".log", ".tmp", ".exe",
	}

	for _, suffix := range skipSuffix {
		if strings.HasSuffix(strings.ToLower(rel), suffix) {
			return true
		}
	}

	return false
}

func pantau(rel string) bool {
	rel = filepath.ToSlash(rel)
	lower := strings.ToLower(rel)
	ext := strings.ToLower(filepath.Ext(lower))

	allwdExt := map[string]bool{
		".py": true, ".go": true, ".md": true, ".toml": true, ".yaml": true, ".yml": true,
	}
	if allwdExt[ext] {
		return true
	}

	base := filepath.Base(lower)

	allwdname := map[string]bool{
		"requirements.txt": true, "requierments.txt": true, "go.mod": true, "go.sum": true, ".gitignore": true, ".env.example": true, "readme.md": true,
	}
	return allwdname[base]
}

func scan(root string) ([]string, error) {
	var files []string

	err := filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		rel := pathRel(root, path)

		if d.IsDir() {
			if Skip(rel) {
				return filepath.SkipDir
			}
			return nil
		}
		if Skip(rel) {
			return nil
		}
		if !pantau(rel) {
			return nil
		}
		info, err := d.Info()
		if err != nil {
			return nil
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return nil
		}
		files = append(files, rel)
		return nil
	})
	if err != nil {
		return nil, err
	}
	sort.Strings(files)
	return files, nil
}

func ringkasScan(files []string) {
	byTop := map[string]int{}
	byExt := map[string]int{}

	for _, f := range files {
		parts := strings.Split(filepath.ToSlash(f), "/")

		top := "(root)"
		if len(parts) > 1 {
			top = parts[0]
		}
		byTop[top]++

		ext := strings.ToLower(filepath.Ext(f))
		if ext == "" {
			ext = "(no ext)"
		}
		byExt[ext]++
	}
	fmt.Println("[SNAPSHOOT] ringkas folder utama:")
	printTopMap(byTop, 10)

	fmt.Println("[SNAPSHOOT] ringkas ekstensi:")
	printTopMap(byExt, 10)
}

func printTopMap(data map[string]int, limit int) {
	type pair struct {
		key   string
		value int
	}
	var pairs []pair
	for k, v := range data {
		pairs = append(pairs, pair{k, v})
	}
	sort.Slice(pairs, func(i, j int) bool {
		if pairs[i].value == pairs[j].value {
			return pairs[i].key < pairs[j].key
		}
		return pairs[i].value > pairs[j].value
	})
	if len(pairs) < limit {
		limit = len(pairs)
	}
	for i := 0; i < limit; i++ {
		fmt.Println(" -", pairs[i].key, "=", strconv.Itoa(pairs[i].value))
	}
}

func hashfile(fullPath string) (string, error) {
	file, err := os.Open(fullPath)
	if err != nil {
		return "", err
	}
	defer file.Close()
	h := sha256.New()

	_, err = io.Copy(h, file)
	if err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func baca(root string, files []string) ([]CatatanFile, error) {
	var hasil []CatatanFile

	for _, rel := range files {
		fullPath := filepath.Join(root, filepath.FromSlash(rel))
		info, err := os.Stat(fullPath)
		if err != nil {
			return nil, fmt.Errorf("gagal baca info file %s: %w", rel, err)
		}
		hash, err := hashfile(fullPath)
		if err != nil {
			return nil, fmt.Errorf("gagal hash file %s: %w", rel, err)
		}
		hasil = append(hasil, CatatanFile{Path: rel, Size: info.Size(), SHA256: hash})
	}
	return hasil, nil
}

func buatSalt() ([]byte, error) {
	salt := make([]byte, 16)
	_, err := rand.Read(salt)
	if err != nil {
		return nil, err
	}
	return salt, nil
}

func kuncipw(password string, salt []byte) []byte {
	data := append([]byte(password), salt...)
	sum := sha256.Sum256(data)
	key := sum[:]

	for i := 0; i < iterasi; i++ {
		h := sha256.New()
		h.Write(key)
		h.Write([]byte(password))
		h.Write(salt)
		key = h.Sum(nil)
	}
	return key
}

func enkripToken(token string, password string) (string, string, string, error) {
	salt, err := buatSalt()

	if err != nil {
		return "", "", "", err
	}
	key := kuncipw(password, salt)

	block, err := aes.NewCipher(key)
	if err != nil {
		return "", "", "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", "", "", err
	}
	nonce := make([]byte, gcm.NonceSize())
	_, err = rand.Read(nonce)
	if err != nil {
		return "", "", "", err
	}
	cipherText := gcm.Seal(nil, nonce, []byte(token), nil)
	saltB64 := base64.StdEncoding.EncodeToString(salt)
	nonceB64 := base64.StdEncoding.EncodeToString(nonce)
	cipherB64 := base64.StdEncoding.EncodeToString(cipherText)

	return saltB64, nonceB64, cipherB64, nil
}

func dekripToken(cfg RuntimeConfig, password string) (string, error) {
	salt, err := base64.StdEncoding.DecodeString(cfg.TokenSaltB64)
	if err != nil {
		return "", fmt.Errorf("salt token rusak")
	}
	nonce, err := base64.StdEncoding.DecodeString(cfg.TokenNonceB64)
	if err != nil {
		return "", fmt.Errorf("nonce token rusak")
	}
	cipherText, err := base64.StdEncoding.DecodeString(cfg.TokenCipherB64)
	if err != nil {
		return "", fmt.Errorf("cipher token rusak")
	}
	key := kuncipw(password, salt)
	block, err := aes.NewCipher(key)

	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	plain, err := gcm.Open(nil, nonce, cipherText, nil)
	if err != nil {
		return "", fmt.Errorf("password salah atau token config rusak")
	}
	return string(plain), nil
}

func datasign(data SnapshootData) ([]byte, error) {
	body := struct {
		Version   int           `json:"version"`
		CreatedAt string        `json:"created_at"`
		Files     []CatatanFile `json:"files"`
	}{
		Version:   data.Version,
		CreatedAt: data.CreatedAt,
		Files:     data.Files,
	}

	return json.Marshal(body)
}

func ttdSnapshoot(data SnapshootData, password string, salt []byte) (string, error) {
	body, err := datasign(data)
	if err != nil {
		return "", err
	}
	key := kuncipw(password, salt)
	mac := hmac.New(sha256.New, key)
	mac.Write(body)

	return hex.EncodeToString(mac.Sum(nil)), nil
}

func verivSnapshoot(data SnapshootData, password string) (bool, error) {
	if data.SaltB64 == "" || data.Signature == "" {
		return false, fmt.Errorf("snapshoot blom punya signature, bikin sapshoot ulang")
	}
	salt, err := base64.StdEncoding.DecodeString(data.SaltB64)
	if err != nil {
		return false, fmt.Errorf("salt snapshoot rusak")
	}
	signBaru, err := ttdSnapshoot(data, password, salt)
	if err != nil {
		return false, err
	}
	return hmac.Equal([]byte(data.Signature), []byte(signBaru)), nil
}

func simpenSnapshoot(root string, catatan []CatatanFile, password string) error {
	dir := dataDir(root)
	err := os.MkdirAll(dir, 0755)
	if err != nil {
		return err
	}
	salt, err := buatSalt()
	if err != nil {
		return err
	}
	data := SnapshootData{Version: 1, CreatedAt: time.Now().Format(time.RFC3339), SaltB64: base64.StdEncoding.EncodeToString(salt), Files: catatan}
	signature, err := ttdSnapshoot(data, password, salt)
	if err != nil {
		return err
	}
	data.Signature = signature
	out, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return err
	}
	target := snapshootPath(root)
	temp := target + ".tmp"
	err = os.WriteFile(temp, out, 0600)
	if err != nil {
		return err
	}
	return os.Rename(temp, target)
}

func loadSnapshoot(root string) (SnapshootData, error) {
	target := snapshootPath(root)

	dataMentah, err := os.ReadFile(target)
	if err != nil {
		return SnapshootData{}, err
	}
	var data SnapshootData
	err = json.Unmarshal(dataMentah, &data)
	if err != nil {
		return SnapshootData{}, err
	}
	if data.Version != 1 {
		return SnapshootData{}, fmt.Errorf("versi snapshot ga di dukung: %d", data.Version)
	}
	return data, nil
}

func SimpenConfig(root string, cfg RuntimeConfig) error {
	dir := dataDir(root)
	err := os.MkdirAll(dir, 0755)

	if err != nil {
		return err
	}
	out, err := json.MarshalIndent(cfg, "", " ")
	if err != nil {
		return err
	}
	target := confgPath(root)
	temp := target + ".tmp"
	err = os.WriteFile(temp, out, 0600)

	if err != nil {
		return err
	}
	return os.Rename(temp, target)
}

func loadRuntime(root string) (RuntimeConfig, error) {
	target := confgPath(root)
	dataMentah, err := os.ReadFile(target)
	if err != nil {
		return RuntimeConfig{}, err
	}
	var cfg RuntimeConfig
	err = json.Unmarshal(dataMentah, &cfg)
	if err != nil {
		return RuntimeConfig{}, err
	}
	if cfg.Version != 1 {
		return RuntimeConfig{}, fmt.Errorf("versi runtime config ga didukung: %d", cfg.Version)
	}
	if cfg.TokenSaltB64 == "" || cfg.TokenNonceB64 == "" || cfg.TokenCipherB64 == "" {
		return RuntimeConfig{}, fmt.Errorf("runtime config blom terenkripsi / token blom ada")
	}
	if cfg.MusicDir == "" {
		return RuntimeConfig{}, fmt.Errorf("MUSIC_DIR kosong di runtime config")
	}
	return cfg, nil
}

func mapCatatan(catatan []CatatanFile) map[string]CatatanFile {
	hasil := map[string]CatatanFile{}
	for _, item := range catatan {
		hasil[item.Path] = item
	}
	return hasil
}

func sensorToken(token string) string {
	if len(token) <= 10 {
		return "********"
	}
	depan := token[:6]
	blkng := token[len(token)-4:]

	return depan + "..." + blkng
}

func perbandingan(lama []CatatanFile, baru []CatatanFile) bool {
	oldMap := mapCatatan(lama)
	newMap := mapCatatan(baru)

	var fileBaru []string
	var fileHilang []string
	var fileBerubah []string

	for path := range newMap {
		if _, ada := oldMap[path]; !ada {
			fileBaru = append(fileBaru, path)
		}
	}
	for path := range oldMap {
		if _, ada := newMap[path]; !ada {
			fileHilang = append(fileHilang, path)
		}
	}
	for path, oldItem := range oldMap {
		newItem, ada := newMap[path]
		if !ada {
			continue
		}
		if oldItem.Size != newItem.Size || oldItem.SHA256 != newItem.SHA256 {
			fileBerubah = append(fileBerubah, path)
		}
	}
	sort.Strings(fileBaru)
	sort.Strings(fileHilang)
	sort.Strings(fileBerubah)

	if len(fileBaru) == 0 && len(fileHilang) == 0 && len(fileBerubah) == 0 {
		fmt.Println("[OK] workspace masih sama")
		return true
	}
	fmt.Println("[WARN] workspace berubah")

	if len(fileBaru) > 0 {
		fmt.Println("\nFile baru:")
		for _, path := range fileBaru {
			fmt.Println(" +", path)
		}
	}
	if len(fileHilang) > 0 {
		fmt.Println("\nFile ngilang:")
		for _, path := range fileHilang {
			fmt.Println(" -", path)
		}
	}
	if len(fileBerubah) > 0 {
		fmt.Println("\nFile berubah:")
		for _, path := range fileBerubah {
			fmt.Println(" *", path)
		}
	}
	fmt.Println("\nSaran:")
	fmt.Println(" git diff")
	return false
}

func cmdSnapshoot(root string) int {
	password := inpkosong("Password snapshoot: ")

	if password == "" {
		fmt.Println("[FAIL] password kosong, snapshoot batal")
		return 1
	}
	fmt.Println("[SNAPSHOOT] scan project...")
	fmt.Println("[SNAPSHOOT] root project:", root)

	files, err := scan(root)
	if err != nil {
		fmt.Println("[FAIL] scan gagal:", err)
		return 1
	}
	fmt.Println("[SNAPSHOOT] total file diawasi:", len(files))
	catatan, err := baca(root, files)
	if err != nil {
		fmt.Println("[FAIL]", err)
		return 1
	}
	ringkasScan(files)

	limit := 10
	if len(catatan) < limit {
		limit = len(catatan)
	}

	fmt.Println("[SNAPSHOOT] contoh sidik jari file:")
	for i := 0; i < limit; i++ {
		hashpndk := catatan[i].SHA256
		if len(hashpndk) > 12 {
			hashpndk = hashpndk[:12]
		}
		fmt.Printf(" - %s | %d bytes | %s\n", catatan[i].Path, catatan[i].Size, hashpndk)

	}

	if len(catatan) > limit {
		fmt.Println(" ...")
	}

	err = simpenSnapshoot(root, catatan, password)
	if err != nil {
		fmt.Println("[FAIL] gagal simpen snapshoot:", err)
		return 1
	}
	fmt.Println("[SNAPSHOOT] kesimpen:", snapshootPath(root))
	return 0
}

func cekWokspace(root string, password string) int {
	snap, err := loadSnapshoot(root)
	if err != nil {
		fmt.Println("[FAIL] gagal baca snapshoot:", err)
		fmt.Println("Jalanin {guard snapshoot} dulu")
		return 1
	}
	valid, err := verivSnapshoot(snap, password)
	if err != nil {
		fmt.Println("[FAIL]", err)
		return 1
	}
	if !valid {
		fmt.Println("[FAIL] password salah atau snapshoot mungkin dah dimanipulasi")
		return 1
	}
	files, err := scan(root)
	if err != nil {
		fmt.Println("[FAIL] scan gagal:", err)
		return 1
	}

	catatanbaru, err := baca(root, files)
	if err != nil {
		fmt.Println("[FAIL]", err)
		return 1
	}
	fmt.Println("[CHECK] snapshoot dibuat", snap.CreatedAt)
	fmt.Println("[CHECK] file di snapshoot:", len(snap.Files))
	fmt.Println("[CHECK] file sekarang:", len(catatanbaru))

	sama := perbandingan(snap.Files, catatanbaru)
	if !sama {
		return 2
	}
	return 0
}

func cmdCheck(root string) int {
	fmt.Println("[CHECK] cek workspace...")
	fmt.Println("[CHECK] root project:", root)

	password := inpkosong("Password snapshoot: ")
	if password == "" {
		fmt.Println("[FAIL] password kosong]")
		return 1
	}
	return cekWokspace(root, password)
}

func cmdRun(root string) int {
	fmt.Println("[RUN] cek keamanan workspace dulu...")
	fmt.Println("[RUN] root project:", root)

	password := inpkosong("Password snapshoot: ")
	if password == "" {
		fmt.Println("[FAIL] password kosong")
		return 1
	}

	status := cekWokspace(root, password)
	if status != 0 {
		fmt.Println("[RUN] batal jalan karena workspace blom aman")
		return status
	}
	fmt.Println("[RUN] workspace aman")

	cfg, err := loadRuntime(root)
	if err != nil {
		fmt.Println("[FAIL] gagal baca runtime config:", err)
		fmt.Println("Jalanin dlu: guard config")
		return 1
	}

	token, err := dekripToken(cfg, password)
	if err != nil {
		fmt.Println("[FAIL] gagal decrypt token:", err)
		return 1
	}

	fmt.Println("[RUN] config kebaca")
	fmt.Println("[RUN] token kebuka", sensorToken(token))
	fmt.Println("[RUN] MUSIC_DIR:", cfg.MusicDir)

	if !folderAda(cfg.MusicDir) {
		fmt.Println("[FAIL] MUSIC_DIR tak ditemukan:", cfg.MusicDir)
		return 1
	}
	if !folderAda(cfg.MusicDir) {
		fmt.Println("[WARN] MUSIC_DIR blom ada file audio:", cfg.MusicDir)
	}
	return jalaninbot(root, token, cfg.MusicDir)
}

func pybin() string {
	env := os.Getenv("PYTHON_BIN")
	if env != "" {
		return env
	}
	if runtime.GOOS == "windows" {
		return "python"
	}
	return "python3"
}

func jalaninbot(root string, token string, musicDir string) int {
	py := pybin()
	cmd := exec.Command(py, "main.py")
	cmd.Dir = root

	cmd.Env = append(os.Environ(), "DISCORD_TOKEN="+token, "MUSIC_DIR="+musicDir)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin

	fmt.Println("[RUN] jalanin:", py, "main.py")

	err := cmd.Run()
	if err == nil {
		return 0
	}
	fmt.Println("[FAIL] gagal jalanin bot:", err)
	return 1
}

func cmdConfig(root string) int {
	fmt.Println("[CONFIG] setup config lokal")
	fmt.Println("[CONFIG] root project:", root)
	fmt.Println("[CONFIG] file config lokal:", confgPath(root))

	password := inpkosong("Password guard:")
	if password == "" {
		fmt.Println("[FAIL] password kosong, config batal")
		return 1
	}

	token := inpkosong("Masukin token DC: ")
	if token == "" {
		fmt.Println("[FAIL] token kosong, config batal")
		return 1
	}
	defaultMusic := filepath.Join(root, "Music")
	fmt.Println("[CONFIG] default MUSIC_DIR:", defaultMusic)

	musicDir := inp("Masukin MUSIC_DIR, atau enter untuk default ./Music: ")
	if musicDir == "" {
		musicDir = defaultMusic
	}
	musicDir, err := filepath.Abs(musicDir)
	if err != nil {
		fmt.Println("[FAIL] path MUSIC_DIR ga valid:", err)
		return 1
	}

	err = os.MkdirAll(musicDir, 0755)
	if err != nil {
		fmt.Println("[FAIL] gagal bikin/buka MUSIC_DIR:", err)
		return 1
	}

	if !folderaud(musicDir) {
		fmt.Println("[WARN] MUSIC_DIR belom ada file audio:", musicDir)
	}

	saltB64, nonceB64, cipherB64, err := enkripToken(token, password)
	if err != nil {
		fmt.Println("[FAIL] gagal enkripsi token:", err)
		return 1
	}

	cfg := RuntimeConfig{
		Version:        1,
		CreatedAt:      time.Now().Format(time.RFC3339),
		TokenSaltB64:   saltB64,
		TokenNonceB64:  nonceB64,
		TokenCipherB64: cipherB64,
		MusicDir:       musicDir,
	}

	cekToken, err := dekripToken(cfg, password)
	if err != nil || cekToken != token {
		fmt.Println("[FAIL] hasil enkripsi token gagal diverif")
		return 1
	}

	err = SimpenConfig(root, cfg)
	if err != nil {
		fmt.Println("[FAIL] gagal simpen config:", err)
		return 1
	}

	fmt.Println("[CONFIG] config terenkripsi kesimpen:", confgPath(root))
	return 0
}

func folderaud(path string) bool {
	extOK := map[string]bool{
		".mp3":  true,
		".wav":  true,
		".flac": true,
		".m4a":  true,
	}
	info, err := os.Stat(path)
	if err != nil || !info.IsDir() {
		return false
	}
	ketemu := false

	_ = filepath.WalkDir(path, func(p string, d os.DirEntry, err error) error {
		if err != nil {
			return nil
		}
		if ketemu {
			return filepath.SkipDir
		}
		if d.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(p))
		if extOK[ext] {
			ketemu = true
		}
		return nil
	})
	return ketemu
}

func main() {
	if len(os.Args) < 2 {
		fmt.Println("Pakai:")
		fmt.Println(" guard snapshoot")
		fmt.Println(" guard check")
		fmt.Println(" guard run")
		fmt.Println(" guard config")
		os.Exit(1)
	}

	root, err := cariRootProject()
	if err != nil {
		fmt.Println("[FAIL]", err)
		os.Exit(1)
	}
	command := os.Args[1]

	switch command {
	case "snapshoot":
		os.Exit(cmdSnapshoot(root))
	case "check":
		os.Exit(cmdCheck(root))
	case "run":
		os.Exit(cmdRun(root))
	case "config":
		os.Exit(cmdConfig(root))
	default:
		fmt.Println("[FAIL] command tak dikenali", command)
		fmt.Println("Pakai: snapshoot / check / run / config")
		os.Exit(1)
	}
}
