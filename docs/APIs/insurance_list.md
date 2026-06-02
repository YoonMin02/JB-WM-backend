요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/insurances
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
insu_cnt	N(2)	현재 페이지 조회 건수
- 한 페이지에 최대 20건 수록 가능
insu_list	<object>	보험목록
-- insu_num	aN(20)	증권번호
- 보험 계약자가 가입한 증권번호
• 마스킹처리 불필요, "-" 제외
-- prod_name	AH(100)	상품명
- 보험 상품의 공식 명칭
-- insu_type	aN(2)	보험종류
- 해당 계약의 보험종류 구분
• 「3.22. 보험종류 코드」 참조
-- insu_status	aN(2)	계약상태
- 현재 주계약의 계약상태
• <코드값>
02 : 정상(보장개시(초회보험료 납입) 및 승낙처리 된 상태)
04 : 실효(계속보험료 연체로 회사가 연체사실 등을 알린 뒤 효력이 상실된 상태)
05 : 만기(보험기간이 경과하여 보험금이 지급되기 전 상태)
06 : 소멸(지급소멸, 만기소멸, 납입면제 등에 따른 소멸 상태. 단, 납입면제 이후 보장이 계속 유지되는 경우에는 정상(02)상태 등록하나, 종신보험의 연금보험 전환 시에는 소멸(06) 사용))
• 만기의 경우, 조회일 기준 5년 이내 만기 계약일 경우에만 회신
• 일부기관의 경우 아래와 같은 계약 존재 시 계약상태(주계약)를 ‘소멸’로 회신
1) 표준화 갱신 상품의 경우 주계약이 ‘소멸’ 상태이나, 특약은 ‘정상’인 계약 존재
2) ‘주계약만기일 < 특약만기일‘ 상품의 경우 주계약이 ‘소멸’ 상태이나, 특약은 ‘정상’인 계약 존재
3) 연금전환 처리되는 계약중 주계약만 전환 시 주계약은 ‘해지’ 또는 ‘소멸’ 상태이나, 특약은 ‘정상’인 계약 존재 → 이 경우 계약 상태를 ‘소멸’로 회신
-- issue_date	N(8)	계약체결일
- 보험계약자와 보험회사의 보험 계약 체결일, 철회 산정기간의 기준일
- 보험갱신 시 증권번호를 새로 발급한 경우 신규 계약체결일을 회신하고, 그렇지 않은 경우 기존 계약체결일을 회신
-- exp_date	N(8)	만기일자
- 보험계약을 보장 받을 수 있는 일자
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
    "insu_cnt": "5",
    "insu_list": [
    { “insu_num": "abcABC123abcABC123ab”,
      "prod_name": "오픈암보험",
      "insu_type": "03",
      "insu_status": "02",
      “issue_date”: “20020202”,
      “exp_date”: “20520202” },
    { … },
    … { … }
    ]
}     