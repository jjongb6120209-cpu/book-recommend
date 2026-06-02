import streamlit as st
import requests
from google import genai
import json

# ==========================================
# 1. API 설정
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
    """[네이버] 정확하고 풍부한 도서 검색 결과를 가져옵니다."""
    if not query:
        return []
    url = "https://openapi.naver.com/v1/search/book.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": 10, "sort": "sim"}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get('items', [])
    except:
        pass
    return []

def fetch_aladdin_toc(isbn):
    """[알라딘] ISBN을 이용해 실제 목차(TOC) 데이터를 연동합니다."""
    if not isbn or not ALADIN_TTB_KEY:
        return ""
    url = "http://www.aladin.co.kr/ttb/api/ItemLookUp.aspx"
    params = {
        "ttbkey": ALADIN_TTB_KEY,
        "ItemId": isbn,
        "ItemIdType": "ISBN",
        "output": "js",
        "Version": "20131101"
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            items = response.json().get('item', [])
            if items:
                return items[0].get('subInfo', {}).get('toc', '')
    except:
        pass
    return ""

def generate_hybrid_recommendations(subject, keyword, level, direction, top_books_with_toc):
    """[최적화 핵심] 2권의 정보를 한 번에 묶어서 제미나이에게 딱 1번만 질문합니다."""
    
    books_input_text = ""
    for idx, item in enumerate(top_books_with_toc):
        book = item['book']
        toc = item['toc'] if item['toc'] else "실시간 목차 연동 실패 (기본 설명을 바탕으로 분석해 주세요)"
        clean_title = book['title'].replace("<b>", "").replace("</b>", "")
        
        books_input_text += f"""
        [도서 번호 {idx+1}]
        - 제목: {clean_title}
        - 저자: {book.get('author', '미상')}
        - 설명: {book.get('description', '설명 없음')}
        - 실제 목차(TOC): {toc}
        ------------------------------------------
        """

    prompt = f"""
    사용자의 주제탐구 요청:
    - 주제: {subject}
    - 핵심 키워드: {keyword}
    - 희망 난이도: {level}
    - 탐구 방향성: {direction}
    
    위에 제공된 {len(top_books_with_toc)}권의 도서 정보를 바탕으로 고등학생 주제탐구(세특)용 맞춤형 분석 보고서를 작성해줘.
    줄글 형태를 절대 피하고, 제공된 양식과 이모지를 그대로 사용해 시각적으로 매우 예쁘게 작성해!
    각 도서별 분석 결과는 반드시 '===BOOK_SPLIT===' 이라는 구분자로 나누어 출력해야 해.
    
    [대상 도서들 정보]
    {books_input_text}
    
    [🚨 지침: 할루시네이션 절대 금지]
    절대 존재하지 않는 가짜 목차나 단원명을 지어내지 마세요. 
    제공된 '실제 목차(TOC)' 내용 중에서 사용자의 '핵심 키워드({keyword})' 및 '탐구 방향성'과 가장 깊게 연관된 단원(챕터)을 찾아내어 매칭하세요.
    
    [출력 양식 (이 양식을 각 책마다 반복하고 책 사이에는 ===BOOK_SPLIT=== 만 넣을 것)]
    ### 🎯 AI 추천 적합도: (별 1~5개로 표현, 예: ⭐⭐⭐⭐⭐)
    
    #### 💡 왜 이 책을 추천하나요?
    (추천 이유를 2~3문장으로 간결하게 작성. ➡️, ✔️ 같은 기호를 문장 앞에 쓸 것.)
    
    #### 🔗 나의 키워드('{keyword}')가 나오는 실제 단원과 탐구 연결고리
    (제공된 '실제 목차' 중 부합하는 단원을 명시하고, 사용자의 탐구 방향성을 어떻게 구체화할 수 있는지 2~3문장으로 논리적 연결고리를 제시할 것. 목차 연동이 안 된 경우 테마를 바탕으로 유추할 것.)
    
    #### 📌 세특 핵심 탐구 포인트
    * 🔹 **포인트 1:** (해당 내용을 바탕으로 고등학생이 수행할 만한 탐구 활동/아이디어를 짧고 명확하게)
    * 🔹 **포인트 2:** (해당 내용을 바탕으로 고등학생이 수행할 만한 탐구 활동/아이디어를 짧고 명확하게)
    * 🔹 **포인트 3:** (해당 내용을 바탕으로 고등학생이 수행할 만한 탐구 활동/아이디어를 짧고 명확하게)
    """
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"추천평 생성 실패: {e}"

# ==========================================
# 3. Streamlit UI 구현
# ==========================================
st.set_page_config(page_title="주제탐구 도서 추천기 v3.0", page_icon="💡", layout="wide")
st.title("💡 주제탐구 도서 추천 프로그램 v3.0 (초고속 하이브리드)")

if not client or not NAVER_CLIENT_ID or not ALADIN_TTB_KEY:
    st.warning("⚠️ Streamlit Secrets 설정을 다시 한번 확인해 주세요!")
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
        
        with st.spinner("데이터베이스에서 최적의 도서를 탐색하는 중..."):
            all_books = []
            seen_links = set()
            
            for q in queries:
                searched = search_naver_books(q)
                for book in searched:
                    if book.get('link') not in seen_links:
                        seen_links.add(book.get('link'))
                        all_books.append(book)
        
        if all_books:
            # 🚨 방어 코드: 알라딘 목차 연동 실패율을 낮추기 위해 우선 상위 책들을 안전하게 확보
            top_books = all_books[:2]
            top_books_with_toc = []
            
            with st.spinner("실시간 책 목차 및 상세 데이터 동기화 중..."):
                for book in top_books:
                    isbn = book.get('isbn', '').split()[-1] if book.get('isbn') else ""
                    toc_data = fetch_aladdin_toc(isbn)
                    top_books_with_toc.append({'book': book, 'toc': toc_data})
            
            with st.spinner("제미나이가 통합 맞춤형 세특 리포트를 작성하는 중..."):
                # 단 1번의 호출로 모든 책의 추천사를 가져옴
                total_result = generate_hybrid_recommendations(subject, keyword, level, direction, top_books_with_toc)
            
            st.success("🎉 분석이 완료되었습니다!")
            st.markdown("---")
            
            # 제미나이가 준 하나의 답변을 구분자(===BOOK_SPLIT===)로 쪼개서 분배
            results_split = total_result.split("===BOOK_SPLIT===")
            
            for idx, item in enumerate(top_books_with_toc):
                book = item['book']
                clean_title = book['title'].replace("<b>", "").replace("</b>", "")
                st.subheader(f"📖 추천 도서 {idx+1}. {clean_title}")
                
                col1, col2 = st.columns([1, 2.5])
                with col1:
                    if book.get('image'):
                        st.image(book['image'], use_container_width=True)
                    else:
                        st.write("📷 표지 이미지 없음")
                    st.caption(f"✍️ 저자: {book.get('author', '미상')}")
                    st.link_button("네이버 책에서 상세보기", book.get('link', 'https://book.naver.com'))
                    
                with col2:
                    # 쪼개진 답변을 순서대로 매칭하여 화면에 출력
                    if idx < len(results_split):
                        st.markdown(results_split[idx].strip())
                    else:
                        st.markdown("AI 분석 로딩에 오류가 발생했습니다. 다시 시도해 주세요.")
                
                st.markdown("---")
        else:
            st.error("❌ 도서를 찾지 못했습니다. '핵심 키워드'를 조금 더 단순하거나 대중적인 단어로 입력해 보세요.")