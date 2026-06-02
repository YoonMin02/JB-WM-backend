요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/cards/issue_info
HTTP Method	GET
요청 메시지 명세
HTTP	항목	값	필수	TYPE (길이)	설명
Header	Authorization	Bearer <access_token>	Y		오픈뱅킹으로부터 전송받은 Access Token을 HTTP Header에 추가 [ scope = cardinfo, sa ]
Parameter	bank_tran_id	“F123456789U4BC34239Z”	Y	AN(20)	거래고유번호(참가기관)
user_seq_no	“U123456789”	Y	AN(10)	사용자일련번호
bank_code_std	“361”	Y	AN(3)	카드사 대표코드(금융기관 공동코드)
member_bank_code	“023”	Y	AN(3)	회원 금융회사 코드(금융기관 공동코드)
card_id	"abcABC123abcABC123abcABC"	Y	aN(64)	카드 식별자 주)
주) 카드목록조회 응답 메시지 상의 카드 식별자
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
card_type	"01"	aN(2)	카드 구분 주1)
settlement_bank_code	"097"	AN(3)	결제은행 코드(금융기관 공동코드)
settlement_account_num	"0001230000123"	AN(16)	결제 계좌번호 주2)
settlement_account_num_masked	"000-1230000-***"	NS*(20)	마스킹된 출력용 결제 계좌번호
issue_date	"20191210"	N(8)	카드 발급일자
(YYYYMMDD)
주1) “01”은 신용, “02”는 체크(직불포함), “03”은 소액신용체크를 의미
주2) 특정 자격요건을 갖춘 이용기관에 선별적 제공(전자금융업자 등)
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
    "card_type": "01",
    "settlement_bank_code": "097",
    "settlement_account_num": "0001230000123",
    "settlement_account_num_masked": "000-1230000-***",
    "issue_date": "20191210"
 
}