# Script thuyết trình — LangGraph Agentic Orchestration (Day 08)

Slide đi kèm: xem link Artifact đã gửi (11 slide, có route rail bên trái đánh dấu tiến độ).
Thời lượng ước tính: 6–8 phút nói + phần hỏi đáp.

---

## Slide 1 — Title
"Chào mọi người, mình trình bày lab Day 08 — xây một agent xử lý ticket hỗ trợ bằng LangGraph.
Đây không phải một chain gọi LLM tuần tự, mà là một state machine thật sự: có định tuyến theo
nội dung ticket, có vòng thử-lại khi lỗi, có bước chờ người duyệt cho hành động rủi ro, và ghi
lại toàn bộ audit trail."

## Slide 2 — Bài toán
"Vấn đề đặt ra: một ticket có thể đi theo 5 hướng khác nhau — câu hỏi đơn giản, cần tra cứu, thiếu
thông tin, có rủi ro như refund hay xoá tài khoản, hoặc là báo lỗi hệ thống. Một prompt chain
tuyến tính không biểu diễn được việc quay lại một bước trước, hay dừng giữa chừng chờ người
duyệt. LangGraph giải quyết bằng cách coi ticket là một *state* đi qua đồ thị các node, với cạnh
điều kiện quyết định bước kế tiếp dựa trên chính state đó — đây cũng là các tiêu chí lab chấm
điểm: state schema đúng, graph compile được, LLM thật ở hai node bắt buộc, và mọi route phải hội
tụ về finalize."

## Slide 3 — Kiến trúc
"Đây là toàn bộ đồ thị — 11 node. Từ intake chuẩn hoá query, đến classify dùng LLM để gán route.
Ba cạnh điều kiện làm nên sự khác biệt so với chain thẳng: route_after_classify rẽ theo ý định,
route_after_evaluate tạo ra vòng thử-lại, và route_after_approval rẽ theo quyết định của người
duyệt. Sơ đồ này mình xuất trực tiếp từ graph đã compile bằng draw_mermaid(), không vẽ tay."

## Slide 4 — State schema
"State được thiết kế lean — chỉ giữ đủ dùng. Các trường như messages, tool_results, errors, events
dùng reducer append để giữ lịch sử không bị ghi đè, phục vụ audit. Các trường điều khiển như route,
attempt, evaluation_result thì overwrite vì chỉ cần giá trị mới nhất. Bốn trường quan trọng —
evaluation_result, pending_question, proposed_action, approval — không có sẵn trong skeleton ban
đầu, mình phải tự phát hiện và bổ sung khi implement từng node cần đến."

## Slide 5 — Case study: giới thiệu
"Case mình chọn để phân tích sâu là S07 — dead letter. Đây là scenario duy nhất override
max_attempts mặc định từ 3 xuống còn 1, buộc vòng retry cạn hạn mức ngay sau lần thử đầu. Mình
chọn case này thay vì case đơn giản hơn vì nó chạm đủ ba lớp thiết kế quan trọng nhất của hệ thống
cùng lúc: lớp đánh giá kết quả tool, lớp giới hạn số lần thử lại, và lớp xử lý khi hệ thống thật
sự bó tay."

## Slide 6 — Case study: đường đi
"Query là 'System failure cannot recover after multiple attempts'. classify_node đọc câu này và
gán route=error — đúng theo thứ tự ưu tiên risky trên tool trên missing_info trên error trên
simple mà mình thiết kế trong prompt. tool_node mô phỏng lỗi transient vì route là error và
attempt nhỏ hơn 2, trả về một chuỗi chứa từ ERROR. evaluate_node chỉ cần kiểm tra substring này để
gán evaluation_result là needs_retry — đây chính là cái 'done check' tạo ra vòng lặp.
route_after_evaluate đưa state quay lại retry, retry_or_fallback_node tăng attempt lên 1, và vì
max_attempts của scenario này là 1 nên route_after_retry so sánh attempt với max_attempts, thấy đã
chạm trần, và đi thẳng vào dead_letter thay vì gọi lại tool. dead_letter trả một câu trả lời trung
thực — không giả vờ đã xử lý xong — rồi mọi route đều hội tụ ở finalize trước khi kết thúc."

## Slide 7 — Phân tích giải pháp
"Ba lớp phòng thủ ở đây không thể làm được nếu dùng một chain tuyến tính.
Lớp một — evaluate gate: tách riêng việc gọi tool khỏi việc đánh giá tool có ổn không thành hai
node độc lập, để có thể quay lại một bước trước đó, điều một LCEL chain không biểu diễn được.
Lớp hai — bounded retry: route_after_retry luôn so attempt với max_attempts trước khi cho phép
quay lại tool. Thiếu điều kiện chặn này thì mọi lỗi transient sẽ lặp vô hạn — đây là pitfall mà
README của lab cảnh báo rõ.
Lớp ba — graceful degradation: dead_letter không phải là fail âm thầm. Nó ghi lỗi vào errors, phát
một event loại escalated, và trả lời khách hàng đúng sự thật rằng chưa xử lý được và đã ghi nhận
để người hỗ trợ tiếp theo xử lý. Toàn bộ vẫn đi qua finalize nên không route nào bị treo giữa
chừng."

## Slide 8 — Nhận xét
"Về điểm mạnh: định tuyến hoàn toàn dựa vào LLM classification cộng với state, không hard-code
theo scenario ID, nên hệ thống vượt qua được cả các scenario ẩn mà lab dùng để chấm điểm. Retry,
HITL, dead-letter đều là node tường minh trong đồ thị nên dễ audit và dễ test riêng từng phần.

Về giới hạn còn tồn tại: evaluate_node hiện tại chỉ là heuristic — kiểm tra substring ERROR — đủ
điểm cơ bản theo yêu cầu lab nhưng là nợ kỹ thuật rõ ràng, nên nâng cấp lên LLM-as-judge.
tool_node là mock, lỗi transient được giả lập bằng đếm attempt chứ chưa phản ánh lỗi API thật như
timeout hay rate limit. Approval mặc định auto-approve trong CI để chạy offline được, HITL thật chỉ
bật khi set biến môi trường, và chưa có vai trò hay phân quyền cho người duyệt. Cuối cùng, latency
trong metrics hiện ghi 0ms vì chưa đo thật, cần bổ sung tracing cho môi trường production."

## Slide 9 — Kết quả
"Tổng kết: 7 trên 7 scenario khớp đúng route kỳ vọng, success rate 100%, trung bình 6.43 node mỗi
scenario. Tổng cộng 3 lượt retry trên toàn bộ scenario, 2 lượt HITL cho hai scenario risky là S04
refund và S06 xoá tài khoản. S05 và S07 đều là route error nhưng khác kết cục: S05 phục hồi sau 2
lần lỗi transient, còn S07 — case mình vừa phân tích — cạn hạn mức sau đúng 1 lần vì
max_attempts bị override."

## Slide 10 — Persistence & extension
"Về khả năng phục hồi trạng thái: mỗi lần chạy có một thread_id riêng gắn với checkpointer.
get_state_history() được gọi sau mỗi run để xác nhận có thể replay lại lịch sử. Extension mình đã
verify là SQLite checkpointer chạy ở chế độ WAL — test tự động tạo một SqliteSaver mới rồi đọc lại
state đã hoàn tất từ database, chứng minh phục hồi vượt ra khỏi một graph object đang nằm trong bộ
nhớ. Ngoài ra còn có sơ đồ Mermaid xuất trực tiếp từ graph đã compile, và HITL thật qua
interrupt() khi cần."

## Slide 11 — Kết & tiếp theo
"Ưu tiên gần nhất: thay mock tool bằng tool hệ thống hỗ trợ thật có xác thực và idempotent, và
nâng evaluate_node lên LLM-as-judge kiểm bằng fixture offline. Xa hơn: thêm vai trò và phân quyền
rõ ràng cho người duyệt HITL, và tracing đo latency thật cho production.
Mình có thể demo trực tiếp bằng make run-scenarios và make grade-local, và sẵn sàng giải thích sâu
hơn bất kỳ route hay failure mode nào nếu mọi người có câu hỏi. Cảm ơn mọi người đã lắng nghe."

---

## Câu hỏi dự đoán (chuẩn bị trước)

**Vì sao evaluate_node không dùng LLM ngay?**
→ README cho phép heuristic ở mức điểm cơ bản, LLM-as-judge là bonus. Mình ưu tiên làm chắc phần
bắt buộc (classify, answer) trước, evaluate nằm trong improvement plan.

**Retry vô hạn thì sao?**
→ Không xảy ra được vì route_after_retry luôn so attempt với max_attempts trước khi cho quay lại
tool; vượt trần là đi thẳng dead_letter.

**HITL thật hoạt động thế nào?**
→ Set LANGGRAPH_INTERRUPT=true, approval_node gọi interrupt() của LangGraph, graph dừng lại chờ
resume với quyết định từ người duyệt thay vì auto-approve.
