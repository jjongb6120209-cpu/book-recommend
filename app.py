import streamlit as st
import requests
from google import genai
import random

# ==========================================
# 1. API 설정 (네이버, 알라딘, 제미나이 듀얼 열쇠)
# ==========================================
NAVER_CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET")
ALADIN_TTB_KEY = st.secrets.get("ALADIN_TTB_KEY")

# 💡 2개의 키를 리스트로 가져옵니다.
API_KEYS = [
    st.secrets.get("GEMINI_API_KEY_1"),
    st.secrets.get("GEMINI_API_KEY_2")
]
# 빈 값 필터링
API_KEYS = [k for k in API_KEYS if k and k != "YOUR_GEMINI_API_KEY"]

def get_gemini_client():
    """[듀얼 엔진] 등록된 2개의 키 중 하나를 50% 확률로 무작위 선택"""
    if not API_KEYS:
        return None
    selected_key = random.choice(API_KEYS)
    return genai.Client(api_key=selected_key)

# ==========================================
# 2. 기능 함수 정의
# ==========================================
def search_naver_books(query):
    """[네이버] 핵심 키워드로 책 목록 검색"""
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
    """[알라딘] ISBN으로 실제 책 목차(TOC) 연동"""
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
    """[호출 분산] 버튼 누를 때마다 무작위로 뽑힌 제미나이 열쇠로 딱 1번 질문 수행"""
    client = get_gemini_client()
    if not client:
        return "추천평 생성 실패: AI 클라이언트를 초기화할 수 없습니다. API 키를 확인하세요."

    books_input_text = ""
    for idx, item in enumerate(top_books_with_toc):
        book = item['book']
        toc = item['toc'] if item['toc'] else "실시간 목차 연동 대기 중 (기본 설명과 책 테마를 바탕으로 분석해 주세요)"
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
    
    위에 제공된 도서 정보를 바탕으로 고등학생 주제탐구(세특)용 맞춤형 분석 보고서를 작성해줘.
    줄글 형태를 절대 피하고, 제공된 양식과 이모지를 그대로 사용해 시각적으로 매우 예쁘게 작성해!
    각 도서별 분석 결과는 반드시 '===BOOK_SPLIT===' 이라는 구분자로 나누어 출력해야 해.
    
    [대상 도서들 정보]
    {books_input_text}
    
    [🚨 지침: 할루시네이션 절대 금지]
    절대 존재하지 않는 가짜 목차나 단원명을 지어내지 마세요. 
    제공된 '실제 목차(TOC)' 내용 중에서 사용자의 '핵심 키워드({keyword})' 및 '탐구 방향성'과 가장 깊게 연관된 단원(챕터)을 찾아내어 매칭하세요.
    
    [출력 양식 (이 양식을 각 책마다 반복하고 책 사이에는 ===BOOK_SPLIT=== 만 넣을 것)]
    ### 🎯 AI 추천 적합도: ⭐⭐⭐⭐⭐
    
    #### 💡 왜 이 책을 추천하나요?
    (추천 이유를 2~3문장으로 간결하게 작성. ➡️, ✔️ 같은 기호를 문장 앞에 쓸 것.)
    
    #### 🔗 나의 키워드('{keyword}')와 탐구 연결고리
    (책의 실제 목차 혹은 핵심 테마 중 부합하는 단원/맥락을 명시하고, 사용자의 탐구 방향성을 어떻게 구체화할 수 있는지 2~3문장으로 논리적 연결고리를 제시할 것.)
    
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
st.set_page_config(page_title="주제탐구 도서 추천기 v4.1", page_icon="💡", layout="wide")
st.title("💡 주제탐구 도서 추천 프로그램 v4.1 (듀얼 분산 엔진)")

if not API_KEYS or not NAVER_CLIENT_ID:
    st.warning("⚠️ Streamlit Secrets에 GEMINI_API_KEY_1, GEMINI_API_KEY_2가 올바르게 등록되어 있는지 확인해 주세요!")
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
        with st.spinner("데이터베이스에서 최적의 도서를 탐색하는 중..."):
            all_books = search_naver_books(keyword)
        
        if all_books:
            top_books = all_books[:2]
            top_books_with_toc = []
            
            with st.spinner("실시간 책 데이터 동기화 및 목차 검증 중..."):
                for book in top_books:
                    isbn = book.get('isbn', '').split()[-1] if book.get('isbn') else ""
                    toc_data = fetch_aladdin_toc(isbn)
                    top_books_with_toc.append({'book': book, 'toc': toc_data})
            
            with st.spinner("분산된 AI 엔진 중 하나를 호출하여 리포트를 작성하는 중..."):
                total_result = generate_hybrid_recommendations(subject, keyword, level, direction, top_books_with_toc)
            
            if "추천평 생성 실패" in total_result:
                st.error("⚠️ 선택된 AI 엔진이 잠시 포화 상태입니다. 한 번만 더 버튼을 눌러주시면 즉시 우회합니다!")
            else:
                st.success("🎉 분산 엔진 분석 완료!")
                st.markdown("---")
                
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
                        if idx < len(results_split):
                            st.markdown(results_split[idx].strip())
                        else:
                            st.markdown("AI 분석 로딩에 오류가 발생했습니다. 다시 시도해 주세요.")
                    
                    st.markdown("---")
        else:
            st.error("❌ 도서를 찾지 못했습니다. '핵심 키워드'를 조금 더 단순하거나 대중적인 단어로 입력해 보세요.")