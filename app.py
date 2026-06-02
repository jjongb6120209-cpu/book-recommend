import streamlit as st
import requests
from google import genai
import os

# ==========================================
# 1. API 설정
# ==========================================
NAVER_CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")

if GEMINI_API_KEY and GEMINI_API_KEY != "YOUR_GEMINI_API_KEY":
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None

# ==========================================
# 2. 기능 함수 정의
# ==========================================
def get_search_keywords(subject, keyword, direction):
    """제미나이를 이용해 검색 키워드를 확장합니다."""
    prompt = f"주제: {subject}, 키워드: {keyword}, 방향: {direction}에 맞는 국내 도서 검색어 3개를 오직 쉼표(,)로만 구분해서 출력해줘. 예: 인공지능, 자율주행, 로봇윤리"
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        keywords = [k.strip() for k in response.text.replace("\n", "").split(',')]
        return [k for k in keywords if k] 
    except Exception as e:
        return [keyword]

def search_naver_books(query):
    """네이버 책 검색 API를 호출합니다."""
    if not query:
        return []
    url = "https://openapi.naver.com/v1/search/book.json"
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    params = {"query": query, "display": 5, "sort": "sim"}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get('items', [])
        else:
            print(f"네이버 API 에러: {response.status_code}")
            return []
    except Exception as e:
        return []

def recommend_single_book(subject, level, direction, book):
    """개별 도서에 대해 시각적이고 가독성 높은 추천사를 작성합니다."""
    clean_title = book['title'].replace("<b>", "").replace("</b>", "")
    
    # 💡 제미나이에게 마크다운, 이모지, 구조화를 강제하는 프롬프트
    prompt = f"""
    사용자의 주제탐구 요청:
    - 주제: {subject}
    - 희망 난이도: {level}
    - 탐구 방향성: {direction}
    
    위 요청을 바탕으로 아래의 책 1권에 대한 고등학생 주제탐구(세특)용 맞춤형 분석을 작성해줘.
    줄글 형태를 절대 피하고, 반드시 아래 제공된 양식과 기호(이모지)를 그대로 사용해서 시각적으로 예쁘게 작성해!
    
    [대상 도서 정보]
    - 제목: {clean_title}
    - 기본 설명: {book['description']}
    
    [출력 양식]
    ### 🎯 AI 추천 적합도: (별 1~5개로 표현, 예: ⭐⭐⭐⭐⭐)
    
    #### 💡 왜 이 책을 추천하나요?
    (여기에 추천 이유를 2~3문장으로 간결하게 작성. ➡️, ✔️ 같은 기호를 문장 앞에 써서 가독성을 높여줘.)
    
    #### 📌 세특 핵심 탐구 포인트
    * 🔹 **포인트 1:** (탐구할 만한 아이디어를 짧고 명확하게)
    * 🔹 **포인트 2:** (탐구할 만한 아이디어를 짧고 명확하게)
    * 🔹 **포인트 3:** (탐구할 만한 아이디어를 짧고 명확하게)
    """
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"추천평 생성 실패: {e}"

# ==========================================
# 3. Streamlit UI 구현
# ==========================================
st.set_page_config(page_title="주제탐구 도서 추천기", page_icon="📚", layout="wide")
st.title("📚 주제탐구 도서 추천 프로그램")

if not client or NAVER_CLIENT_ID == "YOUR_NAVER_CLIENT_ID" or not NAVER_CLIENT_ID:
    st.warning("⚠️ Streamlit Cloud의 Advanced settings -> Secrets 칸에 API 키를 정확히 입력했는지 확인해 주세요!")
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
        
        with st.spinner("네이버에서 책을 찾는 중..."):
            all_books = []
            seen_links = set()
            
            for q in queries:
                searched = search_naver_books(q)
                for book in searched:
                    if book['link'] not in seen_links:
                        seen_links.add(book['link'])
                        all_books.append(book)
        
        if all_books:
            st.success("🎉 추천이 완료되었습니다! AI가 분석한 맞춤형 도서 2권을 확인하세요.")
            st.markdown("---")
            
            # 정확히 2권의 책만 가져오기
            top_books = all_books[:2]
            
            # 💡 책마다 [왼쪽: 사진 / 오른쪽: 추천사] 구조로 반복 출력
            for idx, book in enumerate(top_books):
                clean_title = book['title'].replace("<b>", "").replace("</b>", "")
                st.subheader(f"📖 추천 도서 {idx+1}. {clean_title}")
                
                # 1:2.5 비율로 화면을 두 개의 단(Column)으로 나눔
                col1, col2 = st.columns([1, 2.5])
                
                with col1:
                    # 왼쪽 단: 책 사진과 저자 이름
                    if book.get('image'):
                        st.image(book['image'], use_container_width=True)
                    else:
                        st.write("📷 표지 이미지 없음")
                    st.caption(f"✍️ 저자: {book['author']}")
                    st.link_button("네이버 책에서 상세보기", book['link'])
                    
                with col2:
                    # 오른쪽 단: 제미나이의 시각적 분석 글 (책마다 개별적으로 물어봄)
                    with st.spinner("이 책에 대한 세특 포인트를 뽑아내는 중..."):
                        result = recommend_single_book(subject, level, direction, book)
                        st.markdown(result)
                
                # 책과 책 사이에 구분선 추가
                st.markdown("---")
                
        else:
            st.error("❌ 네이버에서 검색된 책이 없습니다. '핵심 키워드'를 더 단순한 단어로 입력해 보세요.")