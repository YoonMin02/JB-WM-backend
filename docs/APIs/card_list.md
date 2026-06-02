# Card List

오픈뱅킹 카드목록조회 원문 형식입니다. MVP에서는 카드 청구 mock 데이터를 구성하기
위한 카드사/카드상품 메타데이터 참고용으로 사용합니다.

요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/cards
HTTP Method	GET
요청 메시지 명세
HTTP	항목	값	필수	TYPE (길이)	설명
Header	Authorization	Bearer <access_token>	Y		오픈뱅킹으로부터 전송받은 access_token을 HTTP Header에 추가 [scope=cardinfo, sa]
Parameter	bank_tran_id	“F123456789U4BC34239Z”	Y	AN(20)	거래고유번호(참가기관)
user_seq_no	“U123456789”	Y	AN(10)	사용자일련번호
bank_code_std	“361”	Y	AN(3)	카드사 대표코드(금융기관 공동코드)
member_bank_code	“023”	Y	AN(3)	회원 금융회사 코드(금융기관 공동코드)
befor_inquiry_trace_info	“1T201806171”	Y	AN(40)	직전조회추적정보 주)
주) 다음 페이지 요청 시에 직전 조회의 응답에서 얻은 값을 그대로 세팅하며, 최초 요청인 경우에는 파라미터 자체를 설정하지 않음
응답 메시지 명세
HTTP	항목	값	TYPE (길이)	설명
Body	api_tran_id	“2ffd133a-d17a-431d-a6a5”	aNS(40)	거래고유번호(API)
api_tran_dtm	“20190910101921567”	N(17)	거래일시(밀리세컨드)
rsp_code	"A0000"	AN(5)	응답코드(API)
rsp_message	""	AH(300)	응답메시지(API)
bank_tran_id	"F123456789U4BC34239Z"	AN(20)	거래고유번호(참가기관)
bank_tran_date	"20190910"	N(8)	거래일자(참가기관)
bank_code_tran	"097"	AN(3)	응답코드를 부여한 참가기관.표준(대표)코드
bank_rsp_code	"000"	AN(3)	응답코드(참가기관)
bank_rsp_message	""	AH(100)	응답메시지(참가기관)
user_seq_no	"U123456789"	AN(10)	사용자일련번호
next_page_yn	"N"	A(1)	다음페이지 존재여부 주1)
befor_inquiry_trace_info	""	AN(40)	직전조회추적정보
card_cnt	"5"	N(2)	현재 페이지 조회 건수 주2)
card_list	<object>		카드목록
card_id	"abcABC123abcABC123abcABC"	aN(64)	카드 식별자 주3)
card_num_masked	"123456******3456"	NS*(19)	마스킹된 카드번호
card_name	"카드상품명"	AH(50)	상품명
card_member_type	"1"	N(1)	본인/가족 구분 주4)
주1) “Y”인 경우 다음 페이지가 존재하며, “N”인 경우 마지막 페이지
주2) 한 페이지에 최대 20건 수록 가능
주3) 카드기본정보 조회 시 개별 카드 구분을 위해 카드사에서 부여하는 카드의 고유 식별자
주4) “1”인 경우 본인카드, “2”인 경우 가족카드
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
    "card_cnt": "5",
    "card_list": [
    { “card_id": "abcABC123abcABC123abcABC",
    "card_num_masked": "123456******3456",
    "card_name": "카드상품명",
    "card_member_type": "1" },
    { … },
    … { … }
    ]
}
