# Account Balance

오픈뱅킹 계좌 잔액조회 원문 형식입니다. MVP에서는 `AccountBalance` mock DTO를
만들기 위한 금액/날짜/body 항목 참고용으로만 사용합니다.

HTTP URL	https://openapi.openbanking.or.kr/v2.0/account/balance/fin_num
HTTP Method	GET
요청 메시지 명세
HTTP	항목	값	TYPE(길이)	설명
Header	Authorization	Bearer <access_token>		조회서비스 계좌등록 시 오픈뱅킹으로부터 전송받은 access _token을 HTTP Header에 추가
[scope = inquiry ]
Parameter	fintech_use_num	"123456789012345678901234"	AN(24)	핀테크이용번호
bank_tran_id	"F123456789U4BC34239Z"	AN(20)	은행거래고유번호
tran_dtime	"20160310101921"	N(14)	요청일시
응답 메시지 명세
HTTP	항목	값	TYPE(길이)	설명
Body	api_tran_id	AA12349BHZ1324K82AL3	aNS(40)	거래고유번호(API)
api_tran_dtm	"20160310101921567"	N(17)	거래일시
(밀리세컨드)
rsp_code	"A0000"	AN(5)	응답코드(API)
rsp_message	""	AH(100)	응답메시지(API)
bank_tran_id	"12345678901234567890"	AN(20)	거래고유번호
(참가기관)
bank_tran_date	"20160310"	N(8)	거래일자
(참가기관)
bank_code_tran	"098"	AN(3)	응답코드를 부여한 참가기관 표준코드
bank_rsp_code	"000"	AN(3)	응답코드
(참가기관)
bank_rsp_message	""	AN(100)	응답메시지
(참가기관)
bank_name	“오픈은행”	AN(100)	개설기관명
savings_bank_name	“오픈저축은행”	AH(20)	개별저축은행명
fintech_use_num	"123456789012345678901234"	AN(24)	핀테크이용번호
balance_amt	"1000000"	SN(13)	계좌잔액
(-금액가능)
available_amt	"1000000"	N(12)	출금가능금액
account_type	"1"	AN(1)	계좌종류
1:수시입출금,
2:예적금
6:수익증권
product_name	"내맘대로통장"	AH(40)	상품명
account_issue_date	“20190110”	N(8)	계좌개설일
maturity_date	“20200109”	N(8)	만기일
last_tran_date	“20191010”	N(8)	최종거래일
응답 메시지 형태
{
    "api_tran_id": "2ffd133a-d17a-431d-a6a5",
    "api_tran_dtm": "20190910101921567",
    "rsp_code": "A0000",
    "rsp_message": "",
    "bank_tran_id": "F123456789U4BC34239Z",
    "bank_tran_date": "20190910",
    "bank_code_tran": "097",
    "bank_rsp_code": "000",
    "bank_rsp_message": "",
    "bank_name": "오픈은행",
    "fintech_use_num": "123456789012345678901234",
    "balance_amt": "1000000",
    "available_amt": "1000000",
    "account_type": "2",
    "product_name": "알뜰살뜰적금“,
    "account_issue_date": "20190110“,
    "maturity_date": "20200109“,
    "last_tran_date": "20191010“,
}
