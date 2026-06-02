1-1 계좌해지 가능여부 조회
- 이용기관은 금융결제원을 통하여 개설 금융기관으로 계좌해지 가능여부를 조회합니다.
계좌해지가능여부 이미지
- 계좌해지 가능여부 API는 POST 메소드로 호출되며, 상세 스펙 및 호출 예제는 아래와 같습니다.
○ 요청메시지 URL
HTTP URL	https://accountapi.payinfo.or.kr/termination/v1.0/eligibility
HTTP Method	POST
○ 요청메시지 명세
HTTP	항목	값	필수	TYPE
(길이)	설명
Header	api_trx_num	K24101234599123456A0	Y	AN(20)	API 거래고유번호
api_trx_dtm	20241004091059258	Y	Timestamp	거래일시(밀리세컨드)
Body	api_org_code	K241012345	Y	AN(10)	이용기관코드
delegation_yn	Y	Y	A(1)	고객위임여부
delegation_dtm	202410040910	Y	N(12)	고객위임일시
user_name	홍길동	Y	AH(20)	고객명
user_email	abc@gmail.com	Y	E(100)	고객 이메일주소
bank_code	090	Y	N(3)	개설 금융회사 코드
account_num	12345678901234567890	Y	AN(20)	계좌 번호
deposit_sequence	1	N	AN(2)	예금 회차 번호
identity_num	9004151234567	Y	AN(13)	예금주 실명번호
account_type	2	Y	AN(1)	계좌 종류
○ 응답메시지 명세
HTTP	항목	값(예제포함)	TYPE
(길이)	설명
Body	result_type	1	AN(1)	결과코드 구분
result_code	d0000	AN(4)	결과코드
termination_id	123e4567-e89b-12d3-a456-426614174000	ANS(36)	거래검증ID
1-2 잔고이전 수취계좌 확인 조회
- 이용기관은 금융결제원을 통하여 수취계좌 보유기관으로 수취계좌의 정당성 및 입금가능여부 등을 확인합니다.
잔고이전 이미지
- 잔고이전 수취계좌 확인 API는 POST 메소드로 호출되며, 상세 스펙 및 호출 예제는 아래와 같습니다.
○ 요청메시지 URL
HTTP URL	https://accountapi.payinfo.or.kr/termination/v1.0/recipient
HTTP Method	POST
○ 요청메시지 명세
HTTP	항목	값	필수	TYPE
(길이)	설명
Header	api_trx_num	K24101234599123456A0	Y	AN(20)	API 거래고유번호
api_trx_dtm	20241004091059258	Y	Timestamp	거래일시(밀리세컨드)
Body	api_org_code	K241012345	Y	AN(10)	이용기관코드
recv_bank_code	003	Y	N(3)	수취 금융회사 코드
recv_account_num	12345678901234567890	Y	AN(20)	수취 계좌번호
recv_identity_num	9004151234567	Y	AN(13)	수취 계좌 예금주 실명번호
widl_bank_code	090	Y	N(3)	출금 금융회사 코드
widl_account_num	92345678901234567890	N	AN(20)	출금 계좌번호
termination_id	123e4567-e89b-12d3-a456-426614174000	Y	ANS(36)	거래검증ID
○ 응답메시지 명세
HTTP	항목	값(예제포함)	TYPE
(길이)	설명
Body	result_type	1	AN(1)	결과코드 구분
result_code	0000	AN(4)	결과코드
recv_name	홍길동	AH(20)	수취 계좌 예금주명
recv_branch_code	0990000	AN(7)	수취 계좌 관리점 코드
1-3 계좌해지 예상금액 조회
- 이용기관은 금융결제원을 통하여 개설 금융기관으로 계좌해지 시 이자·세금·수수료 등이 계산된 해지 예상금액을 조회
잔고이전 이미지
- 계좌해지 예상금액 API는 POST 메소드로 호출되며, 상세 스펙 및 호출 예제는 아래와 같습니다.
○ 요청메시지 URL
HTTP URL	https://accountapi.payinfo.or.kr/termination/v1.0/status
HTTP Method	POST
○ 요청메시지 명세
HTTP	항목	값	필수	TYPE
(길이)	설명
Header	api_trx_num	K24101234599123456A0	Y	AN(20)	API 거래고유번호
api_trx_dtm	20241004091059258	Y	Timestamp	거래일시(밀리세컨드)
Body	api_org_code	K241012345	Y	AN(10)	이용기관코드
bank_code	090	Y	N(3)	개설 금융회사 코드
account_num	12345678901234567890	Y	AN(20)	계좌번호
deposit_sequence	1	N	AN(2)	예금 회차 번호
identity_num	9004151234567	Y	AN(13)	예금주 실명번호
account_type	2	Y	AN(1)	계좌 종류
recipient_type	1	Y	A(1)	잔고이전 구분
recv_bank_code	003	N	N(3)	수취 금융회사 코드
recv_account_num	12345678901234567890	N	AN(20)	수취 계좌번호
recv_name	홍길동	N	AH(20)	수취 계좌 예금주명
recv_branch_code	0031111	N	AN(7)	수취 계좌 관리점 코드
termination_id	123e4567-e89b-12d3-a456-426614174000	Y	ANS(36)	거래검증ID
○ 응답메시지 명세
HTTP	항목	값(예제포함)	TYPE
(길이)	설명
Body	result_type	1	AN(1)	결과코드 구분
result_code	0000	AN(4)	결과코드
prod_name	수시입출금식 예금	AH(40)	상품명
account_name	홍길동	AH(20)	계좌 예금주명
opening_date	20231118	N(8)	개설 일자
maturity_date	20291118	N(8)	만기 일자
account_balance	1000	N(15)	원금(잔액)
income_tax	0	SN((15)	소득세
local_tax	0	SN((15)	지방 소득세
additional_tax	0	SN((15)	추징 소득세
other_tax	0	SN((15)	기타 세금
interest	10	SN((15)	이자(신탁 이익)
penalty	0	SN((15)	과징금
transfer_fee	50	N(15)	이체 수수료
payment_amount	960	SN((15)	지급액
1-4 계좌해지 및 잔고이전 요청
- 이용기관은 금융결제원을 통하여 제공기관 앞으로 계좌해지·잔고이전 처리를 요청하고, 실시간 처리결과를 수신
잔고이전 이미지
- 계좌해지 예상금액 API는 POST 메소드로 호출되며, 상세 스펙 및 호출 예제는 아래와 같습니다.
○ 요청메시지 URL
HTTP URL	https://accountapi.payinfo.or.kr/termination/v1.0/transfer
HTTP Method	POST
○ 요청메시지 명세
HTTP	항목	값	필수	TYPE
(길이)	설명
Header	api_trx_num	K24101234599123456A0	Y	AN(20)	API 거래고유번호
api_trx_dtm	20241004091059258	Y	Timestamp	거래일시(밀리세컨드)
Body	api_org_code	K241012345	Y	AN(10)	이용기관코드
transfer_type	1	Y	A(1)	처리 구분
bank_code	030	Y	N(3)	개설 금융회사 코드
account_num	12345678901234567890	Y	AN(20)	계좌 번호
deposit_sequence	1	N	AN(2)	예금 회차 번호
identity_num	9004151234567	Y	AN(13)	예금주 실명번호
account_type	2	Y	AN(1)	계좌 종류
recipient_type	1	N	AN(1)	잔고이전 구분
recv_bank_code	003	N	N(3)	수취 금융회사 코드
recv_account_num	12345678901234567890	N	AN(20)	수취 계좌번호
recv_name	홍길동	N	AH(20)	수취 계좌 예금주명
recv_branch_code	0031111	N	AN(7)	수취 계좌 관리점 코드
recv_account_memo	계좌통합이전	N	AH(20)	수취 계좌 기록사항
customer_phone_num	010-1234-5678	Y	AN(14)	고객 전화번호
receipt_yn	N	N	A(1)	기부금 영수증 발급 여부
per_info_yn	N	N	A(1)	제3자 제공동의 여부
sign_type	01	Y	AN(2)	전자서명 인증종류
sign_result	Y	Y	A(1)	전자서명 결과
sign_dtm	202411221044	Y	N(12)	전자서명 일시
termination_id	123e4567-e89b-12d3-a456-426614174000	Y	AN(36)	거래검증ID
○ 응답메시지 명세
HTTP	항목	값(예제포함)	TYPE
(길이)	설명
Body	termination_result_type	1	AN(1)	해지 결과 코드 구분
termination_result_code	0000	AN(4)	해지 결과 코드
recipient_result_type	1	AN(1)	잔고이전 결과 코드 구분
recipient_result_code	0000	AN(4)	잔고이전 결과 코드
prod_name	수시입출금식 예금	AH(40)	상품명
account_name	홍길동	AH(20)	계좌 예금주명
opening_date	20231118	N(8)	개설 일자
maturity_date	20291118	N(8)	만기 일자
account_balance	1000	N(15)	원금(잔액)
income_tax	0	SN(15)	소득세
local_tax	0	SN(15)	지방 소득세
additional_tax	0	SN(15)	추징 소득세
other_tax	0	SN(15)	기타 세금
interest	10	SN(15)	이자(신탁 이익)
penalty	0	SN(15)	과징금
transfer_fee	50	N(15)	이체 수수료
payment_amount	960	SN(15)	지급액
1-5 계좌해지 결과 조회 API
- 이용기관은 금융결제원으로 계좌해지·잔고이전 최종 처리결과를 요청하고 수신
잔고이전 이미지
- 계좌해지 결과 조회 API는 POST 메소드로 호출되며, 상세 스펙 및 호출 예제는 아래와 같습니다.
○ 요청메시지 URL
HTTP URL	https://accountapi.payinfo.or.kr/termination/v1.0/result
HTTP Method	POST
○ 요청메시지 명세
HTTP	항목	값	필수	TYPE
(길이)	설명
Header	api_trx_num	K24101234599123456A0	Y	AN(20)	API 거래고유번호
api_trx_dtm	20241004091059258	Y	Timestamp	거래일시(밀리세컨드)
Body	api_org_code	K241012345	Y	AN(10)	이용기관코드
identity_num	9004151234567	Y	AN(13)	예금주 실명번호
search_startdate	20241008	Y	N(8)	조회 시작일자
search_enddate	20241011	Y	N(8)	조회 종료일자
search_start_num	1	Y	N(6)	지정 번호
data_amount	13	Y	N(6)	요청 데이터 건수
○ 응답메시지 명세
HTTP	항목	값(예제포함)	TYPE
(길이)	설명
Body	result_type	0	AN(1)	결과코드 구분
result_code	0000	AN(4)	결과코드
total_amount	1	N(6)	해지 계좌 총 건수
resp_data_amount	1	N(6)	응답 데이터 건수
termination_list	-	-	해지 계좌 정보 목록
termination_date	20241118	N(8)	해지 신청일자
bank_code	003	N(3)	해지 계좌 금융회사 코드
account_num	1234567890123456	AN(20)	해지 계좌 번호
deposit_sequence	1	AN(2)	예금 회차 번호
account_type	2	AN(1)	계좌 종류
termination_result_type	1	AN(1)	해지 결과 코드 구분
termination_result_code	0000	AN(4)	해지 결과 코드
recipient_result_type	1	AN(1)	잔고이전 결과 코드 구분
recipient_result_code	0000	AN(4)	잔고이전 결과 코드
prod_name	수시입출금식 예금	AH(40)	해지 상품명
opening_date	20231118	N(8)	개설 일자
maturity_date	20291118	N(8)	만기 일자
account_balance	1000	N(15)	원금(잔액)
income_tax	0	SN((15)	소득세
local_tax	0	SN((15)	지방 소득세
additional_tax	0	SN((15)	추징 소득세
other_tax	0	SN((15)	기타 세금
interest	10	SN((15)	이자(신탁 이익)
penalty	0	SN((15)	과징금
transfer_fee	50	N(15)	이체 수수료
payment_amount	960	SN((15)	지급액
recipient_type	T	AN(1)	잔고이전 구분
recv_bank_code	020	N(3)	수취 금융회사 코드
recv_account_num	987654321012345	AN(20)	수취 계좌번호