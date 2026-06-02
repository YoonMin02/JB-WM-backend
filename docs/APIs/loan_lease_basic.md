# Loan and Lease Basic

오픈뱅킹 대출·리스 기본/거래정보 원문 형식입니다. MVP에서는 상환일, 상환방식,
최근 상환 거래를 구성하기 위한 `LoanSummary` mock DTO 기준으로 사용합니다.

요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/loans/basic
HTTP Method	POST
요청 메시지 명세
HTTP	항목	필수	TYPE (길이)	설명
Header	Authorization	Y		오픈뱅킹으로부터 전송받은 Access Token을 HTTP Header에 추가 [ scope = insuinfo, sa ]
- 입력값 : <Beareraccess_token>
Parameter	bank_tran_id	Y	AN(20)	거래고유번호(참가기관)
- 「3.11. 거래고유번호(참가기관) 생성 안내」 참조
bank_code_std	Y	AN(3)	개설기관.표준코드
account_num	Y	AN(16)	조회계좌번호
account_seq	N	AN(3)	조회회차번호
user_seq_no	Y	AN(10)	사용자일련번호
from_date	Y	N(8)	조회시작일자
to_date	Y	N(8)	조회종료일자
befor_inquiry_trace_info	N	AN(20)	직전조회추적정보
- 다음 페이지 요청 시에 직전 조회의 응답에서 얻은 값을 그대로 세팅, 다음 페이지 요청이 아닌 경우에는 파라미터 자체를 설정하지 않음
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
account_num	AN(16)	계좌번호
account_seq	AN(3)	회차번호
repay_date	N(2)	월상환일(DD)
repay_method	aN(2)	상환방식코드주1)
repay_org_code	N(3)	자동이체기관대표코드
- 자동이체 금융기관공동코드
- 가상계좌 입금만 있고 자동이체 서비스를 제공하지 않는 경우 초기값(000) 설정
repay_account_num	AN(16)	상환계좌번호
- 자동이체로 등록된 계좌번호
- 가상계좌입금만 있고 자동이체 서비스를 제공하지 않는 경우 또는 본인소유확인이 불가(타인소유인 경우 등) 한 경우 초기값(SPACE)설정
repay_account_num_masked	NS*(20)	출력용 계좌번호
- 마스킹된 계좌번호
next_repay_date	N(8)	다음이자상환일(YYYYMMDD)
- 다음이자상환예정일(또는 차기결제일)
- 다음이자 상환일 미존재시(만기일 경과 등) 최근 이자 상환일 전송
page_record_cnt	N(2)	현재페이지 레코드건수
- 한 페이지는 최대 20건 가능
next_page_yn	A(1)	다음페이지 존재여부
- 「3.18. 조회서비스 기능 처리 안내」 참조
befor_inquiry_trace_info	AN(20)	직전조회추적정보
res_list		조회된 거래내역
--trans_date	N(8)	거래일자
- 해당계좌에서 거래가 일어난 날짜
- 조회내역은 거래일자 및 거래시간 기준 내림차순
--trans_time	N(6)	거래시간
- 해당계좌에서 거래가 일어난 시간
- 조회내역은 거래일자 및 거래시간 기준 내림차순
--trans_type	aN(2)	거래유형코드
- “01” : 실행, “02” : 상환, “03” : 정정, “99” : 기타
--trans_amt	SN(13)	거래금액
주1) 상환방식코드
상환방식	코드	상환방식	코드
만기일시상환	01	만기지정상환-원리금균등분할상환	07
원금균등분할상환	02	한도거래	07
거치식-원금균등분할상환	03	기타(직접산정)	09
원리금균등분할상환	04	거치식 만기지정상환-원금균등분할상환	10
거치식-원리금균등분할상환	05	거치식 만기지정상환-원리금균등분할상환	11
만기지정상환-원금균등분할상환	06	혼합상환방식	12
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
    "account_num": "0001234567890123",
    “account_seq”: “100”,
    "repay_date": "20221205",
    "repay_method": "01",
    "repay_org_code": "097",
    "repay_account_num": "01220221205",
    "repay_account_num_masked": "01220***205",
    "next_repay_date": "20221205",
    "page_record_cnt ": "5",
    "next_page_yn": "Y",
    "befor_inquiry_trace_info" : "1T201806171",
    "res_list": [
    { 
    "trans_date": "20190910",
    "trans_time": "113000",
    "trans_type": "01",
    "trans_amt": "-450000"
    },
    { … }, … 
    ]
}
