# AccountInfo Integrated Account List

어카운트인포 계좌통합조회 원문 형식입니다. MVP에서는 흩어진 계좌와 유동성 요약을
구성하기 위한 `AccountBalance` 보조 입력으로만 사용합니다.

요청메시지 URL
HTTP URL	https://openapi.openbanking.or.kr/v2.0/accountinfo/list
HTTP Method	POST
요청 메시지 명세
HTTP	항목	값	필수	TYPE(길이)	설명
Header	Authorization	Bearer <access_token>	Y		오픈뱅킹으로부터 전송받은 Access Token을 HTTP Header에 추가
[ scope = sa ]
Body	auth_code	<authorization_code>	Y		사용자정보확인으로 수신한 키
inquiry_bank_type	“1”	Y	AN(1)	금융기관 업권 구분
(1:은행)
org_ainfo_tran_id	“”	N	AN(12)	조회 원거래 전문관리번호
trace_no	“1”	Y	N(6)	지정 번호
inquiry_record_cnt	“30”	Y	N(6)	조회 건수
응답 메시지 명세
HTTP	항목	값(예제포함)	TYPE(길이)	설명
Body	api_tran_id	"2ffd133a-d17a-431d-a6a5"	aNS(40)	거래고유번호(API)
api_tran_dtm	"20190910101921567"	N(17)	거래일시(밀리세컨드)
rsp_code	"A0000"	AN(5)	응답코드(API)
rsp_message	""	AH(300)	응답메시지(API)
ainfo_tran_id		AN(12)	전문관리번호
ainfo_tran_date	"20190910"	N(8)	거래일자(계좌통합)
rsp_type	"0"	AN(1)	응답코드 부여 기관
0:계좌통합센터, 1:금융기관
ainfo_rsp_code	"0000"	AN(4)	응답코드(계좌통합)
ainfo_rsp_message	""	AH(100)	응답메시지(계좌통합)
inquiry_bank_type	“1”	AN(1)	금융기관 구분
exclude_cnt	“2”	N(2)	조회 제외기관 수
exclude_list	<object>		조회 제외기관 목록
--exclude_bank_code	“001”	AN(3)	조회 제외기관 코드
org_ainfo_tran_id	“”	AN(12)	조회 원거래 전문관리번호
trace_no	“1”	N(6)	지정 번호
total_record_cnt	“30”	N(6)	총 조회 건수
page_record_cnt	“30”	N(6)	현재 페이지 조회 건수
res_list	<object>		조회 계좌 목록
--bank_code_std	“097”	AN(3)	개설기관 코드
--activity_type	“A”	A(1)	유형구분
A:활동성계좌, I:비활동성계좌
--account_type	“1”	AN(1)	계좌종류
--account_num	"0001234567890123"	AN(20)	계좌번호
--account_seq	“01”	AN(2)	회차번호
--account_local_code	“0970001”	AN(7)	계좌 관리점 코드
--account_issue_date	“20200918”	N(8)	계좌개설일
--maturity_date	“20210917”	N(8)	만기일
--last_tran_date	“20200924”	N(8)	최종거래일
--product_name	"내맘대로통장"	AH(100)	상품명(계좌명)
--product_sub_name	“부기명”	AH(10)	부기명
--dormancy_yn	“N”	A(1)	휴면계좌 여부
--balance_amt	"1000000"	SN(15)	계좌잔액(-금액가능)
