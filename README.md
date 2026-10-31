# Bloxorz Solver (CSC14003 - Project 1)

Đồ án 1 môn **Cơ sở Trí tuệ Nhân tạo (CSC14003)**: Xây dựng trò chơi giải đố **Bloxorz 3D** kèm các bộ giải tìm kiếm tự động (**BFS**, **DFS**, **UCS**, **A\***) và công cụ thực nghiệm đánh giá hiệu năng (**Benchmark**).

---

## 1. Yêu cầu hệ thống
- **Python 3.11+**
- Các thư viện trong [`requirements.txt`](requirements.txt):
  - `pygame==2.6.1`
  - `PyOpenGL==3.1.9`
- *(Lưu ý trên Linux/Ubuntu)*: Cần có thư viện hệ thống OpenGL GLU (`sudo apt install libglu1-mesa`).

---

## 2. Hướng dẫn cài đặt và chạy Game (How to Run)

Mở terminal / PowerShell tại thư mục chứa mã nguồn (thư mục có file `README.md` và `requirements.txt`):

### Bước 1: Tạo và kích hoạt môi trường ảo (Khuyến nghị)

**Trên Windows (PowerShell):**
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
```

**Trên Linux / macOS:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### Bước 2: Cài đặt thư viện
```bash
pip install -r requirements.txt
```

### Bước 3: Khởi chạy giao diện trò chơi (GUI)
```bash
python -m bloxorz
```

---

## 3. Hướng dẫn điều khiển trong Game (Controls)

| Thao tác / Phím | Chức năng |
| :--- | :--- |
| **Chuột trái (Click Menu)** | Chọn màn chơi (14 màn chơi) và nhấn **PLAY** để bắt đầu |
| **Phím mũi tên (`↑`, `↓`, `←`, `→`)** | Lăn khối hộp theo 4 hướng (tương ứng góc nhìn camera hiện tại) |
| **Phím `Space`** | Chuyển đổi khối lập phương đang điều khiển khi ở trạng thái tách đôi (`SPLIT`) |
| **Kéo chuột trái / Cuộn chuột** | Xoay góc nhìn camera 3D / Phóng to, thu nhỏ bàn chơi |
| **Nút `BFS`, `DFS`, `UCS`, `A*`** *(hoặc phím `1`, `2`, `3`, `4`)* | Gọi thuật toán giải tự động từ đầu màn và phát lại (Replay) từng bước đi |
| **Nút `Restart`** *(hoặc phím `R`)* | Chơi lại màn hiện tại |
| **Phím `N`** | Chuyển nhanh sang màn chơi tiếp theo |
| **Nút `Menu`** *(hoặc phím `Esc`)* | Quay lại màn hình Menu chọn màn chơi |

---

## 4. Chạy thực nghiệm đánh giá thuật toán (Benchmark)

Để chạy đánh giá cả 4 thuật toán (**BFS**, **DFS**, **UCS**, **A\***) trên toàn bộ 14 màn chơi và xuất bảng thống kê / biểu đồ:

```bash
python -m bloxorz.benchmark -o benchmark_output -r 3
```
- Kết quả gồm bảng tổng hợp trên terminal, file `results.csv`, `results.json`, `report.md` và 4 biểu đồ so sánh (`time_comparison`, `memory_comparison`, `expanded_comparison`, `length_comparison`) được lưu trong thư mục `benchmark_output/`.

---

## 5. Cấu trúc thư mục

```text
├── bloxorz/               # Mã nguồn chính của chương trình
│   ├── __main__.py        # Điểm khởi chạy chương trình (python -m bloxorz)
│   ├── core/              # Logic cốt lõi: trạng thái (State), bản đồ (Level), luật chơi (Rules)
│   ├── gui/               # Giao diện đồ họa 3D OpenGL + Pygame
│   ├── solvers/           # 4 thuật toán tìm kiếm: bfs.py, dfs.py, ucs.py, astar.py
│   └── benchmark/         # Công cụ đo đạc thực nghiệm và vẽ biểu đồ
├── levels/                # 14 màn chơi định dạng JSON (level01_basic.json .. level14_labyrinth.json)
├── assets/                # Tài nguyên hình ảnh / textures cho giao diện 3D
├── tests/                 # Unit tests
├── requirements.txt       # Các thư viện cần thiết để chạy chương trình
└── README.md              # Hướng dẫn cài đặt và chạy chương trình
```

---

## Kiểm tra code trước khi commit
``` powershell
pre-commit run --all-files
pytest --cov=bloxorz
```

## Quy trình
1. Không push thẳng lên `main`
2. Tạo nhánh bằng: `git checkout -b feature/ten-viec`
3. Commit rồi push lên nhánh: `git push -u origin feature/ten-viec`
4. Mở Pull Request trên Github
5. Chờ CI xanh và cả nhóm thống nhất approve (hoặc ít nhất là supervisor) rồi sau đó mới được merge

## Xử lí khi pre-commit chặn commit
 - Nếu Hook báo failed và tự sửa file -> git add . -> rồi commit lại
 - Nếu flake8 báo lỗi -> Sửa code theo dòng được báo
