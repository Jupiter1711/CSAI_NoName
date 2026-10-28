# Contract: phần core dùng chung

Tài liệu này mô tả **interface** giữa phần game (`bloxorz/core`) với solver, GUI và benchmark.
Ai làm phần nào cũng chỉ cần đọc file này, không cần hiểu bên trong `rules.py`.

Muốn đổi bất kỳ thứ gì trong file này thì mở PR riêng và báo cả nhóm trước.

---

## 1. Định dạng level (`levels/*.json`)

```json
{
  "name": "Level 3 - Switches",
  "grid": [
    "####..#####..######",
    "#S##BB#####BB######",
    "####BB##X##BB###G##",
    "#O##..#####..######"
  ],
  "open_bridges": [],
  "switches": [
    {"pos": [3, 1], "mode": "toggle", "bridges": [[1, 4], [1, 5], [2, 4], [2, 5]]},
    {"pos": [2, 8], "mode": "open",   "bridges": [[1, 11], [1, 12], [2, 11], [2, 12]]}
  ]
}
```

| Ký tự | Ô |
|---|---|
| `.` | void (không có gạch) |
| `#` | gạch thường |
| `S` | điểm xuất phát (là gạch thường) |
| `G` | lỗ đích |
| `F` | gạch giòn (fragile) |
| `B` | ô cầu (mở/đóng tùy trạng thái) |
| `O` | soft switch |
| `X` | heavy switch |
| `P` | split switch |

- Tọa độ luôn là `[hàng, cột]`, bắt đầu từ 0, hàng tăng khi đi xuống.
- Mỗi level có đúng một `S` và một `G`. Hàng ngắn hơn sẽ được tự đệm thêm `.`.
- `open_bridges`: các ô cầu mở sẵn lúc bắt đầu, không ghi thì tất cả đóng.
- Mỗi ô `O`, `X`, `P` phải có một mục trong `switches`. Loại switch lấy theo ký tự trên grid.
  - `O` / `X`: `mode` là `toggle` (mặc định), `open` hoặc `close` (hai cái sau là permanent); `bridges` là danh sách ô cầu bị ảnh hưởng.
  - `P`: `targets` là 2 ô mà hai cube được dịch chuyển tới.

Load level: `load_level("levels/level01_basic.json")`. Level sai định dạng sẽ báo `LevelError` kèm lý do.

---

## 2. State

```python
class State(NamedTuple):
    kind: str      # "S" đứng, "H" nằm ngang, "V" nằm dọc, "X" đã tách 2 cube
    r1: int
    c1: int
    r2: int
    c2: int
    bridges: int   # bitmask: bit i = 1 nghĩa là ô cầu thứ i đang mở
```

- `(r1, c1)` luôn là ô trên cùng / trái nhất. Với `"S"` thì `(r2, c2) == (r1, c1)`.
- `state.cells` trả về các ô khối đang chiếm (1 ô nếu đứng, 2 ô nếu nằm hoặc đã tách).
- Ô cầu được đánh số theo thứ tự đọc grid (trái sang phải, trên xuống dưới): `level.bridges[i]` là ô ứng với bit `i`.
- State **hashable** và **bất biến**: bỏ thẳng vào `set` / làm key `dict` được. Không sửa state, chỉ tạo state mới.
- Hai state cùng vị trí nhưng khác `bridges` là hai state khác nhau.

---

## 3. Problem API (dành cho người làm solver)

```python
from bloxorz.core import BloxorzProblem

problem = BloxorzProblem.from_file("levels/level01_basic.json")

problem.initial_state()      # -> State
problem.is_goal(state)       # -> bool
problem.successors(state)    # -> list[(action, next_state, cost)]
problem.level                # Level: level.goal, level.tile(r, c), level.rows, ...
```

- `successors` chỉ trả về nước đi **hợp lệ**, đã xử lý hết void, fragile, switch, cầu, split.
- **Action** là chuỗi:
  - khối bình thường: `"U"`, `"D"`, `"L"`, `"R"`
  - khi đã tách: `"1U"`, ..., `"2R"` (cube 1 là cube có `(r1, c1)`, cube 2 là cube có `(r2, c2)`)
- Lời giải trả về là `list[str]` các action, ví dụ `["R", "D", "D", "R", "R", "D", "R"]`.
- Đổi lượt điều khiển giữa 2 cube (phím Space) **không** phải action và không tính vào số nước.

### Cost (UCS)

Mặc định mỗi nước có cost 1. Người làm UCS truyền hàm cost riêng:

```python
def my_cost(level, state, action, next_state) -> float:
    ...

problem = BloxorzProblem.from_file(path, cost_fn=my_cost)
```

### Heuristic (A*)

Heuristic viết trong file của A*, dạng `h(problem, state) -> float`, lấy đích từ `problem.level.goal`.
Nhớ rằng heuristic phải admissible **theo đúng cost function đang dùng**.

---

## 4. Solver trả về gì (dành cho benchmark)

Mỗi solver là một hàm `solve(problem) -> SearchResult`, trong đó:

```python
@dataclass
class SearchResult:
    path: list[str] | None   # None nếu không có lời giải
    expanded: int            # số node đã expand
    cost: float              # tổng cost của path
```

Thời gian và bộ nhớ đỉnh do benchmark đo bên ngoài (`time.perf_counter`, `tracemalloc`) để mọi solver được đo cùng một cách.
**Expanded** = số lần lấy một state ra khỏi frontier để sinh successors (đếm thống nhất như vậy cho cả 4 thuật toán).

Kiểm tra lời giải có đúng không:

```python
from bloxorz.core import replay
states = replay(problem.level, result.path)   # báo lỗi nếu có nước không hợp lệ
assert problem.is_goal(states[-1])
```

---

## 5. Dành cho GUI

```python
from bloxorz.core import initial_state, step, is_goal, actions

state = initial_state(level)
nxt = step(level, state, "R")   # None nghĩa là rơi -> thua
```

`replay(level, path)` trả về danh sách state theo từng bước, dùng để animate lời giải.

---

## 6. Luật đã chốt

1. Switch kích hoạt khi khối **lăn tới** ô switch. Mỗi lần lăn khối luôn rời hết các ô cũ, nên không có chuyện "đứng yên trên switch".
2. Nếu khối nằm đè lên 2 switch cùng lúc thì cả hai cùng kích hoạt.
3. Nếu switch vừa đóng cầu mà khối đang đè lên cầu đó thì khối rơi, nước đi không hợp lệ.
4. Fragile chỉ cấm **khối đứng thẳng**. Cube đơn (sau khi tách) đi lên fragile được.
5. Cube đơn chỉ kích hoạt được soft switch, không kích hoạt heavy hay split, và không thắng được.
6. Hai cube tự gộp lại thành khối nằm ngay khi đứng kề nhau (chung cạnh). Vì vậy hai cube không bao giờ đè lên nhau.
7. Khối nằm ngang qua lỗ đích không thắng, chỉ đứng thẳng trên `G` mới thắng.
