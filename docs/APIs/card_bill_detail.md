# Card Bill Detail

오픈뱅킹 카드청구상세정보 원문 형식입니다. MVP에서는 의료비/고정비 카드 지출을
분류하기 위한 `CardBill.details` mock DTO 기준으로 사용합니다.

요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/cards/bills/detail
HTTP Method	GET
요청 메시지 명세
HTTP	항목	값	필수	TYPE (길이)	설명
Header	Authorization	Bearer <access_token>	Y		오픈뱅킹으로부터 전송받은 Access Token을 HTTP Header에 추가 [ scope = cardinfo, sa ]
Parameter	bank_tran_id	“F123456789U4BC34239Z”	Y	AN(20)	거래고유번호(참가기관)
user_seq_no	“U123456789”	Y	AN(10)	사용자일련번호
bank_code_std	“361”	Y	AN(3)	카드사 대표코드(금융기관 공동코드)
member_bank_code	“023”	Y	AN(3)	회원 금융회사 코드(금융기관 공동코드)
charge_month	“202106	Y	N(6)	청구년월(YYYYMM) 주)
settlement_seq_no	“001”	Y	N(4)	결제순번 주)
befor_inquiry_trace_info	“1T201806171”	N	AN(40)	직전조회추적정보
주) 카드청구기본정보조회 응답 메시지 상의 청구년월 및 결제순번
응답 메시지 명세
HTTP	항목	값	TYPE (길이)	설명
Body	api_tran_id	"2ffd133a-d17a-431d-a6a5"	aNS(40)	거래고유번호(API)
api_tran_dtm	"20190901101921567"	N(17)	거래일시(밀리세컨드)
rsp_code	"A0000"	AN(5)	응답코드(API)
rsp_message	""	AH(300)	응답메시지(API)
bank_tran_id	"F123456789U4BC34239Z"	AN(20)	거래고유번호(참가기관)
bank_tran_date	"20190901"	N(8)	거래일자(참가기관)
bank_code_tran	"097"	AN(3)	응답코드를 부여한 참가기관.표준(대표)코드
bank_rsp_code	"000"	AN(3)	응답코드(참가기관)
bank_rsp_message	""	AH(100)	응답메시지(참가기관)
user_seq_no	"U123456789"	AN(10)	사용자일련번호
next_page_yn	"N"	A(1)	다음페이지 존재여부
befor_inquiry_trace_info	""	AN(40)	직전조회추적정보
bill_detail_cnt	"5"	N(2)	현재 페이지 조회 건수 주1)
bill_list	<object>		청구상세목록
card_value	"abcABC123abcABC123abcABC"	aN(64)	카드 식별값
paid_date	"20190110“	N(8)	사용일자 (YYYYMMDD)
paid_time	“102030”	N(6)	사용시간 (hhmmss)
paid_amt	“456000”	SN(13)	이용금액
(원/KRW)(-금액가능) 주2)
merchant_name_masked	“오픈**”	AH(40)	마스킹된 가맹점명
credit_fee_amt	“456”	SN(13)	신용판매 수수료
(원/KRW)(-금액가능) 주3)
product_type	"01"	aN(2)	상품 구분 주4)
주1) 한 페이지에 최대 20건 수록 가능
주2) 신용정보법에 의해 가족카드 이용내역은 미제공되므로 이용금액 합계가 청구기본정보조회의 청구금액과 다를 수 있음
주3) 복수 개의 수수료가 존재하는 경우, 수수료 합계
주4) “01”은 일시불, “02”는 신용판매할부, “03”은 현금서비스 의미
응답 메시지 형태
{
    "api_tran_id": "2ffd133a-d17a-431d-a6a5",
    "api_tran_dtm": "20190901101921567",
    "rsp_code": "A0000",
    "rsp_message": "",
    "bank_tran_id": "F123456789U4BC34239Z",
    "bank_tran_date": "20190901",
    "bank_code_tran": "097",
    "bank_rsp_code": "000",
    "bank_rsp_message": "",
    "user_seq_no": "U123456789",
    "next_page_yn": "N",
    "befor_inquiry_trace_info": "",
    "bill_detail_cnt": "5",
    "bill_detail_list": [
    { "card_value": "abcABC123abcABC123abcABC",
    "paid_date": "20190110“,
    “paid time”: “102030”
    "paid_amt": “456000”,
    "merchant_name": “오픈**”,
    "credit_fee_amt": “456”,
    "product_type": “01” },
    { … }, … { … }
    ]
}
