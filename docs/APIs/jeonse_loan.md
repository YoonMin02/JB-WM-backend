요청 메시지 명세
HTTP	항목	항목명	필수	min	max	타입	데이터
header	api_trx_num	API 거래고유번호	Y	20	20	String	AN(20)
api_trx_dtm	거래일시(밀리세컨드)	Y	17	17	String	Timestamp
Body	api_org_code	플랫폼이용기관코드	Y	10	10	String	AN(10)
delegation_yn	고객위임여부	Y	1	1	String	A(1)
delegation_dtm	고객위임일시	Y	10	10	String	N(10)
customer_identity_num	개인실명번호	Y	13	13	String	AN(13)
bank_code	보유기관 금융회사 코드	Y	3	3	String	N(3)
sub_bank_code	하위 보유기관 코드	Y	3	3	String	N(3)
loan_contract_id	대출식별번호	Y	-	20	String	AN(20)
loan_info_request_date	조회요청일자	Y	8	8	String	N(8)
응답 메시지 명세
HTTP	항목	항목명	필수	min	max	타입	데이터
header	api_trx_num	API 거래고유번호	Y	20	20	String	AN(20)
api_trx_dtm	거래일시(밀리세컨드)	Y	17	17	String	Timestamp
Body	loan_repayment_id	API 조회고유번호	Y	12	12	String	AN(12)
repayment_avail_yn	상환가능여부	Y	1	1	String	AN(1)
denial_code	상환불가사유코드	Y	2	2	String	AN(2)
loan_repayment_penalty_fee	중도상환수수료	Y	-	15	String	N(15)
loan_interestrate_type	대출금리형태	Y	1	1	String	A(1)
loan_interestrate_variation_cycle	대출금리 변동주기	N	-	3	String	N(3)
loan_fixedRate_apply_period	고정금리 적용기간	N	-	3	String	N(3)
guarantee_agency_code	보증기관코드	Y	3	3	String	AN(3)