# A* solver với 3D reverse BFS

File [`astaralgo.py`](./astaralgo.py) cài đặt A* cho Bloxorz và sử dụng lại
API của core:

- `BloxorzProblem.initial_state()` để lấy trạng thái bắt đầu.
- `BloxorzProblem.is_goal()` để kiểm tra trạng thái đích.
- `BloxorzProblem.successors()` để sinh các nước đi hợp lệ, bao gồm luật
  switch, cầu, fragile và trạng thái tách cube.
- `State` cùng các hằng số `STANDING`, `HORIZONTAL`, `VERTICAL`, `SPLIT`.

## 1. Reverse BFS 3D

`bfs(problem)` xây dựng khoảng cách tối thiểu từ goal về mọi trạng thái block
thông thường trong không gian ba chiều:

```text
(row, column, kind)
```

BFS bắt đầu từ:

```text
(goal_r, goal_c, "S")
```

Các cạnh được sinh ngược theo hướng lăn:

| Kind hiện tại | Trạng thái tiền nhiệm |
|---|---|
| `S` | `V(r-2,c)`, `V(r+1,c)`, `H(r,c-2)`, `H(r,c+1)` |
| `H` | `S(r,c-1)`, `S(r,c+2)`, `H(r-1,c)`, `H(r+1,c)` |
| `V` | `S(r-1,c)`, `S(r+2,c)`, `V(r,c-1)`, `V(r,c+1)` |

Một trạng thái được đưa vào BFS nếu:

1. Tọa độ hợp lệ trên level; `Level.tile()` được gọi trong `try/except`.
2. Các ô mà block chiếm không phải vực `.`.
3. Nếu block nằm ngang hoặc dọc, ô thứ hai cũng phải hợp lệ.
4. Block đứng `S` không được đứng trên gạch giòn `F`.

Kết quả được lưu trong `_BFS_CACHE`. Khóa cache là `id(problem)`, vì vậy BFS
chỉ chạy một lần cho mỗi object problem.

## 2. Heuristic

### Block thông thường

Với trạng thái `S`, `H` hoặc `V`, heuristic tra khoảng cách từ BFS cache.
Khoảng cách BFS được ép về `float`.

Nếu trạng thái không có trong cache, heuristic dùng fallback:

```text
Manhattan(goal, position) / 2.0
```

### Block đã tách

Với trạng thái `X`, gọi:

```text
d1 = Manhattan(goal, cube_1)
d2 = Manhattan(goal, cube_2)
d_cubes = Manhattan(cube_1, cube_2)
```

Sau đó trả về:

```text
max(
    max(d1, d2) / 2.0,
    (d_cubes - 1) / 2.0 + min(d1, d2) / 2.0
)
```

Giá trị cuối cùng luôn có kiểu `float`.

## 3. Vòng lặp A*

Frontier dùng heap với item:

```text
(f_score, counter, state)
```

`counter` tăng dần để xử lý trường hợp hai state có cùng `f_score` mà không
cần so sánh trực tiếp các object `State`.

A* duy trì:

- `g_score`: chi phí tốt nhất đã biết từ start.
- `came_from`: predecessor và action để dựng lại path.
- `closed_set`: các state đã được pop và expand.
- `expanded`: số state chưa từng đóng được pop khỏi frontier.

Khi tìm thấy goal, `solve(problem)` trả về:

```python
SearchResult(path, expanded, cost)
```

Nếu frontier cạn mà không có lời giải, kết quả là:

```python
SearchResult(None, expanded, 0.0)
```

Các action và cost vẫn được lấy từ `problem.successors()`, nên solver không
tái cài đặt hoặc làm thay đổi luật di chuyển trong core.
