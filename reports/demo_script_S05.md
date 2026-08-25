# Script thuyết trình — Case S05_error (demo trực tiếp)

Dùng khi trình bày kèm terminal chạy thật `python demo_case.py S05_error`.
Thời lượng: ~2–3 phút.

---

## 1. Giới thiệu case
"Case mình chọn để demo trực tiếp là S05 — lỗi hệ thống có thể phục hồi. Query là
'Timeout failure while processing request', max_attempts để mặc định là 3. Mình chọn case
này vì nó là scenario duy nhất đi trọn vẹn cả vòng lặp retry: gọi tool, đánh giá, thất bại,
thử lại, rồi thành công — chứ không tắt sớm như case dead-letter."

## 2. Chạy demo
(Gõ trực tiếp trên terminal, đã activate `.venv`)
```bash
python demo_case.py S05_error
```
"Đây là script nhỏ mình viết để gọi thẳng `build_graph()` — graph thật, LLM thật, không
mock kết quả. Nó in ra từng audit event graph phát ra, theo đúng thứ tự đi qua node."

## 3. Đọc kết quả cùng khán giả
"Nhìn vào node path: đầu tiên `classify` gán route là error. Điều thú vị là route error
không đi thẳng vào `tool` — nó đi qua `retry` trước, tăng attempt lên 1, rồi mới gọi `tool`.
Đây là quyết định thiết kế có chủ đích trong graph, không phải bug.

Lần gọi `tool` đầu tiên thất bại vì attempt=1 nhỏ hơn 2 — tool mô phỏng lỗi transient.
`evaluate` đọc kết quả, thấy có chữ ERROR, gán needs_retry. Cạnh điều kiện đưa state quay
lại `retry` lần hai, attempt tăng lên 2. Lần gọi `tool` thứ hai thành công vì attempt không
còn nhỏ hơn 2 nữa. `evaluate` gán success, và cuối cùng `answer` được gọi — dùng LLM thật để
sinh câu trả lời."

## 4. Điểm nhấn — câu trả lời của LLM
"Chú ý câu trả lời cuối: LLM không giả vờ mọi thứ suôn sẻ ngay từ đầu. Nó nói rõ có một lần
timeout ở lần thử thứ hai, nhưng lần thứ ba thì tra cứu thành công. Đây là vì prompt của
`answer_node` yêu cầu: chỉ khẳng định đã thực hiện xong nếu tool context nói SUCCESS, và
tool_results ở đây có cả dòng ERROR lẫn SUCCESS — LLM tổng hợp trung thực cả hai."

## 5. Chốt
"Đây chính là giá trị của LangGraph so với một chain gọi LLM một lần: đồ thị cho phép quay
lại một bước trước đó khi kết quả chưa đạt, có giới hạn rõ ràng để không lặp vô hạn, và toàn
bộ quá trình được ghi lại thành audit trail có thể trình bày trực tiếp như thế này."

---

## Nếu bị hỏi thêm

**Vì sao route error không gọi tool ngay mà qua retry trước?**
→ Đây là thiết kế trong `graph.py`: `error → retry → [conditional] → tool`. Route error coi
như "đã biết là có khả năng lỗi", nên đưa qua retry trước để attempt counter luôn phản ánh
đúng số lần đã cố gắng trước khi tool chạy lần đầu.

**Demo này có gọi API thật không?**
→ Có, dùng `OPENAI_API_KEY` trong `.env`, cả `classify_node` (structured output) và
`answer_node` đều gọi LLM thật, không mock.
