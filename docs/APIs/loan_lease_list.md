# Loan and Lease List

오픈뱅킹 대출·리스 목록조회 원문 형식입니다. MVP에서는 고객 부채 목록과 대출 유형을
정리하기 위한 `LoanSummary` mock DTO 기준으로 사용합니다.

요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/loans
HTTP Method	GET
요청 메시지 명세
HTTP	항목	필수	TYPE (길이)	설명
Header	Authorization	Y		오픈뱅킹으로부터 전송받은 Access Token을 HTTP Header에 추가 [ scope = insuinfo, sa ]
- 입력값 : <Beareraccess_token>
Parameter	bank_tran_id	Y	AN(20)	거래고유번호(참가기관)
- 「3.11. 거래고유번호(참가기관) 생성 안내」 참조
user_seq_no	Y	AN(10)	사용자일련번호
bank_code_std	Y	AN(3)	보험사 대표코드 (금융기관 공동코드)
- 「3.3. 금융기관코드」 의 ‘보험사’ 참조
befor_inquiry_trace_info	N	AN(40)	직전조회추적정보
- 다음 페이지 요청 시에 직전 조회의 응답에서 얻은 값을 그대로 세팅
- 최초 요청인 경우에는 파라미터 자체를 설정하지 않음
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
next_page_yn	A(1)	다음페이지 존재여부
- “Y”:다음 페이지 존재, “N”:마지막 페이지)
- 「3.18. 조회서비스 기능 처리 안내」 - 「다음페이지 처리」 항목 참조
befor_inquiry_trace_info	AN(40)	직전조회추적정보
- 다음페이지 존재여부가 “Y”이고, 다음 페이지 조회를 요청할 때 본 필드를 요청 파라미터에 추가
loan_cnt	N(2)	현재 페이지 조회 건수
- 한 페이지에 최대 20건 수록 가능
loan_list	<object>	대출·리스목록
-- account_num(선택)	AN(16)	계좌번호주1)
-캐피탈사에서 고객이 이용하는 상품 또는 서비스에 부여하는 식별번호(“-” 제외)
-- account_seq(선택)	AN(3)	회차번호주1)
- 동일 계좌번호 내에서 회차별 특성이 상이한 상품인 경우 회차번호가 제공되며, 계좌번호 + 회차번호 조합으로 관리
-- account_num_masked	NS*(20)	출력용 계좌번호
- 마스킹된 계좌번호
-- prod_name	AH(100)	상품명
- 해당 계좌의 공식 상품 명칭
-- account_type	aN(4)	계좌구분코드주2)
- 해당계좌의 유형
-- account_status	aN(2)	계좌상태코드주2)
- 현재 계좌상태
주1) 특정 자격요건을 갖춘 이용기관에 선별적 제공(자체인증기관, 소액해외송금업자 등)
주2) 계좌구분 및 계좌상태
계좌 유형	계좌구분코드	계좌상태코드
대출
상품	신용대출	신용대출	3100	01:활동(사고포함)
학자금대출	3150
전세자금대출	3170
담보대출	예・적금담보대출	3200
유가증권(주식, 채권, 펀드 등)담보대출	3210
주택담보대출	3220
주택외 부동산(토지,상가등)담보대출	3230
지급보증(보증서) 담보대출	3240
보금자리론	3245
학자금(지급보증담보)대출	3250
주택연금대출	3260
전세자금(보증서, 질권 등)대출	3270
전세보증금 담보대출	3271
기타 담보대출	3290
보험계약대출	3400
할부금융	신차 할부금융	3500
중고차 할부금융	3510
기타 할부금융	3590
리스	금융리스	3700
운용리스	3710
기타	3999
응답 메시지 형태
{
    "api_tran_id": "2ffd133a-d17a-431d-a6a5",
    "api_tran_dtm": "20220910101921567",
    "rsp_code": "A0000",
    "rsp_message": "",
    "bank_tran_id": "F123456789U4BC34239Z",
    "bank_tran_date": "20220910",
    "bank_code_tran": "097",
    "bank_rsp_code": "000",
    "bank_rsp_message": "",
    "user_seq_no": "U123456789",
    "next_page_yn": "N",
    "befor_inquiry_trace_info": "",
    "loan_cnt": "5",
    "loan_list": [
    { “account_num": "0001230000123",
      “account_num_seq”: “001”,
      "account_num_masked": "000-1230000-***",
      "prod_name": "오픈대출",
      "account_type": "3271",
      "account_status": "01" },
    { … },
    … { … }
    ]
}
