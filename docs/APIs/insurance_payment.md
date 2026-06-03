# Insurance Payment

오픈뱅킹 보험납입정보조회 원문 형식입니다. MVP에서는 월 보험료와 납입 방식이
현금흐름에 주는 영향을 계산하기 위한 mock DTO 기준으로 사용합니다.

요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/insurances/payment
HTTP Method	POST
요청 메시지 명세
HTTP	항목	필수	TYPE (길이)	설명
Header	Authorization	Y		오픈뱅킹으로부터 전송받은 Access Token을 HTTP Header에 추가 [ scope = insuinfo, sa ]
- 입력값 : <Beareraccess_token>
Parameter	bank_tran_id	Y	AN(20)	거래고유번호(참가기관)
- 「3.11. 거래고유번호(참가기관) 생성 안내」 참조
bank_code_std	Y	AN(3)	보험사 대표코드 (금융기관 공동코드)
- 「3.3. 금융기관코드」 의 ‘보험사’ 참조
user_seq_no	Y	AN(10)	사용자일련번호
insu_num	Y	aN(20)	증권번호
- 보험 계약자가 가입한 증권번호
응답 메시지 명세
HTTP	항목	TYPE (길이)	설명
Body	api_tran_id	aNS(40)	거래고유번호(API)
api_tran_dtm	N(17)	거래일시(밀리세컨드)
rsp_code	AN(5)	응답코드(API)
rsp_message	AH(300)	응답메시지(API)
bank_tran_id	AN(20)	거래고유번호(참가기관)
bank_tran_date	N(8)	거래일자(참가기관)
bank_code_tran	AN(3)	응답코드를 부여한 참가기관.표준(대표)코드
bank_rsp_code	AN(3)	응답코드(참가기관)
bank_rsp_message	AH(100)	응답메시지(참가기관)
user_seq_no	AN(10)	사용자일련번호
pay_due	aN(2)	납입기간구분
- 납입만기기간구분
- “01”:일시납 , “02”:연납, “03:세납
pay_cycle	AN(2)	납입주기
- 납입주기구분
- “1M”:매월, “2M”:2개월납, “3M”:3개월, “6M”:6개월
“1Y”:연단위, “99”:일시납
pay_date	N(2)	납입일자(DD)
- 보험 계약서 상, 계약자가 작성한 지정 이체 혹은 결제일자
- 자동이체, 급여이체 등 날짜 지정 가능한 납입방법 외의 계약(납입예정일자 미존재)의 경우는 “00” 회신
- 납입일자를 숫자(DD)가 아닌 “말일”로 지정한 기관의 경우, “99” 회신
pay_end_date	N(8)	납입종료일자(YYYYMMDD)
- 보험료납입종료일
pay_amt	N(12)	납입보험료(KRW)
- 납입주기에 따른 보험료 납입금액
- 해외통화금액인 경우 원화(KRW)로 환산 표기
pay_org_code	N(3)	납입기관 대표코드
- 보험료 납입방법이 자동이체인 경우 자동이체가 이루어지는 금융기관 공동(대표)코드를 설정
pay_account_num(선택)	Nsp(16)	납입 계좌번호주1)
- 자동이체방식이 계좌이체인 경우 납입 계좌번호 설정
- 카드납부/기타인 경우 미설정
pay_account_num_masked	NS*(20)	출력용 납입 계좌/카드번호
- 자동이체 방식이 계좌이체인 경우 마스킹된 출력용 납입 계좌를 설정
- 카드납부인 경우 마스킹된 카드번호(-제외)를 설정
is_auto_pay	A(1)	자동대출납입 신청 여부
- “Y”:신청, “N”:미신청
주1) 특정 자격요건을 갖춘 이용기관에 선별적 제공(자체인증기관, 소액해외송금업자 등)
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
    “pay_due”: “01”,
    “pay_cycle”: “99”,
    "pay_date": "01",
    "pay_end_date": "20551231",
    "pay_amt“: "1000000",
    “pay_org_code”: “097”,
    "pay_account_num": "0001230000123",
    "pay_account_num_masked": "000-1230000-***"
}
