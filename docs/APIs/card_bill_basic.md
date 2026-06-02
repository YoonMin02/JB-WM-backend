# Card Bill Basic

오픈뱅킹 카드청구기본정보 원문 형식입니다. MVP에서는 다음 달 카드 결제 예정액과
현금흐름 압박을 계산하기 위한 `CardBill` mock DTO 기준으로 사용합니다.

요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/cards/bills
HTTP Method	GET
요청 메시지 명세
HTTP	항목	값	필수	TYPE (길이)	설명
Header	Authorization	Bearer <access_token>	Y		오픈뱅킹으로부터 전송받은 Access Token을 HTTP Header에 추가 [ scope = cardinfo, sa ]
Parameter	bank_tran_id	“F123456789U4BC34239Z”	Y	AN(20)	거래고유번호(참가기관)
user_seq_no	“U123456789”	Y	AN(10)	사용자일련번호
bank_code_std	“361”	Y	AN(3)	카드사 대표코드(금융기관 공동코드)
member_bank_code	“023”	Y	AN(3)	회원 금융회사 코드(금융기관 공동코드)
from_month	“202005”	Y	N(6)	조회 시작월(YYYYMM)
to_month	“202105”	Y	N(6)	조회 종료월(YYYYMM)
befor_inquiry_trace_info	“1T201806171”	N	AN(40)	직전조회추적정보
응답 메시지 명세
HTTP	항목	값	TYPE (길이)	설명
Body	api_tran_id	"2ffd133a-d17a-431d-a6a5"	aNS(40)	거래고유번호(API)
api_tran_dtm	"20190910101921567"	N(17)	거래일시(밀리세컨드)
rsp_code	"A0000"	AN(5)	응답코드(API)
rsp_message	""	AH(300)	응답메시지(API)
bank_tran_id	"F123456789U4BC34239Z"	AN(20)	거래고유번호(참가기관)
bank_tran_date	"20190910"	N(8)	거래일자(참가기관)
bank_code_tran	"097"	AN(3)	응답코드를 부여한 참가기관.표준(대표)코드
bank_rsp_code	"000"	AN(3)	응답코드(참가기관)
bank_rsp_message	""	AH(100)	응답메시지(참가기관)
user_seq_no	"U123456789"	AN(10)	사용자일련번호
next_page_yn	"N"	A(1)	다음페이지 존재여부
befor_inquiry_trace_info	""	AN(40)	직전조회추적정보
bill_cnt	"5"	N(2)	현재 페이지 조회 건수 주1)
bill_list	<object>		청구목록
charge_month	"201912"	N(6)	청구년월
settlement_seq_no	"001"	N(4)	결제순번 주2)
card_id	"abcABC123abcABC123abcABC"	aN(64)	카드 식별자
charge_amt	"456000"	SN(13)	청구금액(-금액가능) 주3)
settlement_day	"25"	N(2)	결제일
settlement_date	"20191226"	N(8)	결제년월일
(실제 결제일)
credit_check_type	"01"	aN(2)	신용/체크 구분 주4)
주1) 한 페이지에 최대 20건 수록 가능
주2) 일부 카드사는 결제일을 복수로 지정 가능하며, 이 경우 동일 청구년월에 결제순번을 다르게 설정하여 여러 건의 청구내역을 반환할 수 있음(결제순번이 없는 일반적인 경우에는 “0”)
주3) 가족카드 청구금액 포함
주4) 청구서가 신용카드 청구정보인지 체크카드 청구정보인지 구분(“01”은 신용, “02”는 체크, “03”은 신용/체크혼용 의미)
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
    "user_seq_no": "U123456789",
    "next_page_yn": "N",
    "befor_inquiry_trace_info": "",
    "bill_cnt": "5",
    "bill_list": [
    { "charge_month": "201912",
    "settlement_seq_no": "001",
    “card_id": "abcABC123abcABC123abcABC",
    "charge_amt": "456000",
    "settlement_day": "25",
    "settlement_date": "20191226",
    "card_type": "01" },
    { … }, … { … }
    ]
}
