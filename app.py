import streamlit as st
import requests
from google import genai
import os

# ==========================================
# 1. API 설정 (네이버, 알라딘, 제미나이 모두 연동)
# ==========================================
NAVER_CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET")
ALADIN_TTB_KEY = st.secrets.get("ALADIN_TTB_KEY")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None

# ==========================================
# 2. 기능 함수 정의
# ==========================================
def get_search_keywords(subject, keyword, direction):
    """제미나이를 이용해 네이버 검색용 키워드를 확장합니다."""
    prompt = f"주제: {subject}, 키워드: {keyword}, 방향: {direction}에 맞는 국내 도서 검색어 3개를 오직 쉼표(,)로만 구분해서 출력해줘. 예: 인공지능, 자율주행, 로봇윤리"
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        keywords = [k.strip() for k in response.text.replace("\n", "").split(',')]
        return [k for k in keywords if k] 
    except Exception as e:
        return [keyword]

def search_naver_books(query):
    """[1단계] 네이버 책 검색 API를 통해 광범위하고 정확한 도서 리스트를 사냥합니다."""
    if not query:
        return []
    url = "https://openapi.naver.com/v1/search/book.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": 8, "sort": "sim"}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get('items', [])
        else:
            return []
    except Exception as e:
        return []

def fetch_aladdin_toc(isbn):
    """[2단계] 네이버가 찾아온 책의 ISBN을 이용해 알라딘에서 '실제 목차(TOC)'를 쏙 빼옵니다."""
    if not isbn or not ALADIN_TTB_KEY:
        return ""
    
    url = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
    params = {
        "ttbkey": ALADIN_TTB_KEY,
        "ItemId": isbn,
        "ItemIdType": "ISBN", # ISBN 번호로 책을 정밀 타격 조회
        "output": "js",
        "Version": "20131101" # 목차를 가져오기 위한 필수 버전
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            items = response.json().get('item', [])
            if items:
                # 알라딘 상세 정보 내부의 목차(toc) 텍스트 반환
                return items[0].get('subInfo', {}).get('toc', '')
    except Exception as e:
        pass
    return ""

def recommend_single_book(subject, keyword, level, direction, book, toc_data):
    """[3단계] 네이버 데이터와 알라딘 목차를 모두 쥐고 제미나이가 초정밀 추천사를 작성합니다."""
    clean_title = book['title'].replace("<b>", "").replace("</b>", "")
    book_description = book.get('description', '설명 없음')
    
    # 알라딘 목차가 비어있을 경우를 대비한 방어 코드
    if not toc_data:
        toc_data = "이 책의 공식 목차 정보가 실시간 연동되지 않았습니다. 책 소개를 기반으로 분석해 주세요."

    prompt = f"""
    사용자의 주제탐구 요청:
    - 주제: {subject}
    - 핵심 키워드: {keyword}
    - 희망 난이도: {level}
    - 탐구 방향성: {direction}
    
    위 요청과 제공된 책의 '기본 정보' 및 알라딘 연동 '실제 목차'를 바탕으로, 고등학생 주제탐구(세특)용 맞춤형 분석을 작성해줘.
    줄글 형태를 절대 피하고, 제공된 양식과 이모지를 그대로 사용해 시각적으로 예쁘게 작성해!
    
    [대상 도서 정보]
    - 제목: {clean_title}
    - 기본 설명: {book_description}
    - 연동된 실제 목차(TOC): {toc_data}
    
    [🚨 지침: 할루시네이션 절대 금지]
    절대 존재하지 않는 가짜 목차나 단원명을 지어내지 마세요. 
    반드시 제공된 '연동된 실제 목차(TOC)'에 적힌 내용 중에서 사용자의 '핵심 키워드({keyword})' 및 '탐구 방향성'과 가장 깊게 연관된 단원(챕터)을 찾아내어 매칭하세요.
    만약 목차 정보가 부실하다면, 기본 설명을 바탕으로 어떤 파트와 엮일 수 있는지 합리적인 맥락을 유추해서 적어주세요.
    
    [출력 양식]
    ### 🎯 AI 추천 적합도: (별 1~5개로 표현, 예: ⭐⭐⭐⭐⭐)
    
    #### 💡 왜 이 책을 추천하나요?
    (추천 이유를 2~3문장으로 간결하게 작성. ➡️, ✔️ 같은 기호를 문장 앞에 쓸 것.)
    
    #### 🔗 나의 키워드('{keyword}')가 나오는 실제 단원과 탐구 연결고리
    (제공된 '실제 목차' 혹은 책의 핵심 테마 중 어떤 단원/챕터에 이 내용이 부합하는지 명시하고, 그 단원을 통해 사용자의 탐구 방향성을 어떻게 구체화할 수 있는지 2~3문장으로 논리적 연결고리를 제시할 것.)
    
    #### 📌 세특 핵심 탐구 포인트
    * 🔹 **포인트 1:** (해당 단원의 내용을 바탕으로 고등학생이 수행할 만한 탐구 활동/아이디어를 짧고 명확하게)
    * 🔹 **포인트 2:** (해당 단원의 내용을 바탕으로 고등학생이 수행할 만한 탐구 활동/아이디어를 짧고 명확하게)
    * 🔹 **포인트 3:** (해당 단원의 내용을 바탕으로 고등학생이 수행할 만한 탐구 활동/아이디어를 짧고 명확하게)
    """
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"추천평 생성 실패: {e}"

# ==========================================
# 3. Streamlit UI 구현
# ==========================================
st.set_page_config(page_title="주제탐구 도서 추천기 하이브리드", page_icon="💡", layout="wide")
st.title("💡 주제탐구 도서 추천 프로그램 v2.5 (네이버 X 알라딘 하이브리드)")

# API 키 점검
if not client or not NAVER_CLIENT_ID or not ALADIN_TTB_KEY:
    st.warning("⚠️ Streamlit Secrets에 NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, ALADIN_TTB_KEY, GEMINI_API_KEY가 모두 등록되어 있는지 확인해 주세요!")
    st.stop()

with st.form("search_form"):
    subject = st.text_input("📌 탐구 주제", placeholder="예: 자율주행 자동차의 윤리적 딜레마")
    keyword = st.text_input("🔑 핵심 키워드 (가급적 단어 위주로 입력)", placeholder="예: 자율주행, 트롤리 딜레마")
    level = st.selectbox("📊 난이도", ["초급", "중급", "고급"])
    direction = st.text_area("💡 탐구 방향성", placeholder="예: 프로그래밍 관점과 책임 소재를 다루고 싶음.")
    submitted = st.form_submit_button("추천 도서 찾기 🚀")

if submitted:
    if not subject or not keyword or not direction:
        st.error("모든 칸을 채워주세요!")
    else:
        with st.spinner("AI가 최적의 검색 키워드를 생성하는 중..."):
            queries = get_search_keywords(subject, keyword, direction)
            if keyword not in queries:
                queries.append(keyword)
        
        with st.spinner("네이버 데이터베이스에서 최적의 책을 사냥하는 중..."):
            all_books = []
            seen_links = set()
            
            for q in queries:
                searched = search_naver_books(q)
                for book in searched:
                    if book.get('link') not in seen_links:
                        seen_links.add(book.get('link'))
                        all_books.append(book)
        
        if all_books:
            st.success("🎉 추천 도서 엄선 완료! 실시간 목차 정보를 크로스 체크하여 분석합니다.")
            st.markdown("---")
            
            # 네이버가 찾은 상위 2권 선정
            top_books = all_books[:2]
            
            for idx, book in enumerate(top_books):
                clean_title = book['title'].replace("<b>", "").replace("</b>", "")
                st.subheader(f"📖 추천 도서 {idx+1}. {clean_title}")
                
                # 1:2.5 레이아웃 분할
                col1, col2 = st.columns([1, 2.5])
                
                with col1:
                    # 왼쪽: 네이버 데이터 기반의 표지 이미지와 정보 출력
                    if book.get('image'):
                        st.image(book['image'], use_container_width=True)
                    else:
                        st.write("📷 표지 이미지 없음")
                    st.caption(f"✍️ 저자: {book.get('author', '미상')}")
                    st.link_button("네이버 책에서 상세보기", book.get('link', 'https://book.naver.com'))
                    
                with col2:
                    # 오른쪽: 네이버가 준 ISBN으로 알라딘 목차를 찾은 뒤 제미나이에게 토스!
                    isbn = book.get('isbn', '').split()[-1] if book.get('isbn') else ""
                    
                    with st.spinner("알라딘 인프라에서 실제 목차 데이터를 연동하는 중..."):
                        toc_data = fetch_aladdin_toc(isbn)
                    
                    with st.spinner("연동된 목차를 바탕으로 세특 보고서 맵핑 중..."):
                        result = recommend_single_book(subject, keyword, level, direction, book, toc_data)
                        st.markdown(result)
                
                st.markdown("---")
        else:
            st.error("❌ 도서를 찾지 못했습니다. '핵심 키워드'를 더 범용적인 단어로 입력해 보세요.")