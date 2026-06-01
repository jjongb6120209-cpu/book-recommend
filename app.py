import streamlit as st
import requests
from google import genai

# ==========================================
# 1. API 설정 (깃허브 배포를 위해 Secrets 방식으로 변경)
# ==========================================
import os

NAVER_CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY")
# Gemini 클라이언트 초기화
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
        # 줄바꿈이나 공백을 제거하고 쉼표로 분리
        keywords = [k.strip() for k in response.text.replace("\n", "").split(',')]
        return [k for k in keywords if k] # 빈 문자열 제외
    except Exception as e:
        # 에러 발생 시 사용자가 입력한 기본 키워드 반환
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
            # 터미널 창에 네이버 API 에러 코드를 출력하여 디버깅을 돕습니다.
            print(f"네이버 API 에러 코드: {response.status_code}, 메시지: {response.text}")
            return []
    except Exception as e:
        print(f"네이버 요청 중 네트워크 에러: {e}")
        return []

def recommend_final_books(subject, level, direction, book_list):
    """최종 추천 도서 평을 작성합니다."""
    books_text = ""
    for i, book in enumerate(book_list):
        books_text += f"[{i+1}] 제목: {book['title']}, 저자: {book['author']}, 설명: {book['description']}\n\n"
    
    prompt = f"""
    사용자의 주제탐구 요청:
    - 주제: {subject}
    - 희망 난이도: {level}
    - 탐구 방향성: {direction}
    
    아래 도서 목록 중 가장 잘 맞는 책을 2권 골라 고등학생 주제탐구 보고서(세특)용 추천사를 작성해줘.
    추천 이유와 책에서 발췌하면 좋은 '탐구 포인트/아이디어'를 상세히 적어줘.
    
    {books_text}
    """
    try:
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
        return response.text
    except Exception as e:
        return f"최종 추천평 생성 실패: {e}"

# ==========================================
# 3. Streamlit UI 구현
# ==========================================
st.set_page_config(page_title="주제탐구 도서 추천기", page_icon="📚")
st.title("📚 주제탐구 도서 추천 프로그램")

# API 키가 Secrets에서 잘 넘어왔는지 직관적으로 확인하는 조건문으로 변경
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
            # 안전장치: 사용자가 입력한 원래 키워드도 검색 목록에 강제로 추가
            if keyword not in queries:
                queries.append(keyword)
            st.write(f"🔍 **확인된 검색어 목록:** {queries}")
        
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
            with st.spinner("제미나이가 맞춤형 추천사를 작성하는 중..."):
                result = recommend_final_books(subject, level, direction, all_books)
                st.success("🎉 추천이 완료되었습니다!")
                st.markdown("---")
                st.markdown(result)
        else:
            st.error("❌ 여전히 네이버에서 검색된 책이 없습니다. API 키(ID/Secret)가 정확한지 다시 확인해 보거나, '핵심 키워드'를 더 단순한 단어(예: 인공지능, 윤리)로 입력해 보세요.")