# Account Transaction List

오픈뱅킹 계좌 거래내역조회 원문 형식입니다. MVP에서는 의료비, 고정비, 현금흐름
이벤트를 감지하기 위한 `AccountTransaction` mock DTO의 기준으로 사용합니다.

요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/account/transaction_list/fin_num
HTTP Method	GET
요청 메시지 명세
HTTP	항목	값	TYPE(길이)	설명
Header	Authorization	Bearer <access_token>		조회서비스 계좌등록 시
오픈뱅킹으로부터 전송받은
access _token을
HTTP Header에 추가
[scope = inquiry]
Parameter	bank_tran_id	"F123456789U4BC34239Z"	AN(20)	은행거래고유번호
fintech_use_num	"123456789012345678901234"	AN(24)	핀테크이용번호
inquiry_type	"A"	A(1)	조회구분코드
A:All,I:입금, O:출금
inquiry_base	“D”	A(1)	조회기준코드
D:일자, T:시간
from_date	"20160404"	N(8)	조회시작일자
from_time	"100000"	N(6)	조회시작일자
to_date	"20160405"	N(8)	조회종료일자
to_time	"110000"	N(6)	조회종료시간
sort_order	"D"	A(1)	정렬순서
D:Descending,A:Ascending
tran_dtime	"20160310101921"	N(14)	요청일시
befor_inquiry_trace_info	"123"	AN(20)	직전조회추적정보
응답 메시지 명세
HTTP	항목	값	TYPE(길이)	설명
Body	api_tran_id	"AA12349BHZ1324K82AL3"	aNS(40)	거래고유번호(API)
api_tran_dtm	"20160310101921567"	N(17)	거래일시
(밀리세컨드)
rsp_code	"A0000"	AN(5)	응답코드(API)
rsp_message	""	AH(300)	응답메시지(API)
bank_tran_id	"12345678901234567890"	AN(20)	거래고유번호
(참가기관)
bank_tran_date	"20160310"	N(8)	거래일자
(참가기관)
bank_code_tran	"098"	AN(3)	응답코드를 부여한
참가기관 표준코드
bank_rsp_code	"000"	AN(3)	응답코드
(참가기관)
bank_rsp_message	""	AN(100)	응답메시지
(참가기관)
bank_name	“오픈은행”	AH(20)	개설기관명
savings_bank_name	“오픈저축은행”	AH(20)	개별저축은행명
fintech_use_num	"123456789012345678901234"	AN(24)	핀테크이용번호
balance_amt	"1000000"	SN(2)	계좌잔액
(-금액가능)
page_record_cnt	"25"	N(2)	현재페이지 레코드 건수 주1)
next_page_yn	"Y"	A(1)	다음 페이지
존재여부
res_list	<object>		조회된 거래내역
tran_date	"20160310"	N(8)	거래일자
tran_time	"113000"	N(6)	거래시간
inout_type	"입금"	AH(8)	입출금구분
("입금", "출금")
tran_type	"현금"	AH(10)	거래구분 주2)
print_content	"통장인자내용"	AH(20)	통장인자내용
tran_amt	"450000"	N(12)	거래금액
after_balance_amt	"-1000000"	SN(13)	거래 후 잔액
(-금액가능)
주1) 한 페이지는 최대 25건
주2) 현금, 대체, 급여, 타행환, F/B출금 등
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
    "page_record_cnt ": "25",
    "next_page_yn": "Y",
    "befor_inquiry_trace_info" : "1T201806171",
    "res_list": [
    {
    "tran_date": "20190910",
    "tran_time": "113000",
    "inout_type": "입금",
    "tran_type": "현금",
    "printed_content": "통장인자내용",
    "tran_amt": "450000",
    "after_balance_amt": "-1000000",
    "branch_name": "분당점“
    },
    { … },
    …
    { … }
    ]
}
