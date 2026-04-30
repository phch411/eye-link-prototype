import streamlit as st
from supabase import create_client
import pandas as pd

# 1. 페이지 설정 (로그인 전용 레이아웃)
st.set_page_config(page_title="Eye-Link 시스템", layout="centered")

# 2. Supabase 연결 설정 (Secrets 활용)
# Streamlit Cloud의 Settings -> Secrets에 아래 정보가 입력되어 있어야 합니다.
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase = create_client(url, key)

# 3. 세션 상태 초기화 (로그인 여부 확인용)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

# 4. 데이터 불러오기 함수
def load_data():
    try:
        # 'students' 테이블에서 실시간 데이터 호출
        response = supabase.table("students").select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

# 5. [화면 1] 로그인 페이지 함수
# --- [화면 1] 로그인 페이지 함수 (수정본) ---
def show_login_page():
    _, col2, _ = st.columns([1, 2, 1])
    
    with col2:
        st.write("") 
        st.title("🛡️ Eye-Link")
        st.subheader("학교 관리자 로그인")
        
        with st.container(border=True):
            school_id = st.text_input("학교 식별 코드", placeholder="ID를 입력하세요")
            password = st.text_input("비밀번호", type="password")
            login_btn = st.button("시스템 접속", use_container_width=True)
            
            if login_btn:
                # 1. Supabase의 users 테이블에서 해당 ID와 PW가 일치하는 데이터 찾기
                try:
                    user_query = supabase.table("users")\
                        .select("*")\
                        .eq("school_id", school_id)\
                        .eq("password", password)\
                        .execute()
                    
                    # 2. 결과가 존재하면 로그인 성공
                    if len(user_query.data) > 0:
                        st.session_state['logged_in'] = True
                        st.session_state['school_name'] = user_query.data[0]['school_name']
                        st.success(f"{st.session_state['school_name']}님, 환영합니다!")
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
                except Exception as e:
                    st.error(f"로그인 처리 중 오류가 발생했습니다: {e}")

# 6. [화면 2] 메인 대시보드 페이지 함수
def show_main_dashboard():
    # 로그아웃 버튼 (사이드바)
    if st.sidebar.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.rerun()

    st.title("👁️ Eye-Link 실시간 모니터링")
    
    # 데이터 로드
    df = load_data()

    if not df.empty:
        # 상단 알림 (MVP 1: 즉각적인 인식)
        danger_count = len(df[df['status'] == 'Red'])
        if danger_count > 0:
            st.error(f"🚨 경고: 현재 {danger_count}명의 학생이 이탈 상태입니다!")
        else:
            st.success("✅ 현재 모든 학생이 안전 거리 내에 있습니다.")

        # 지도 표시 (MVP 2: 실시간 맵)
        st.subheader("📍 학생 실시간 위치")
        # lat, lon 컬럼이 있어야 함
        st.map(df)

        # 학생별 상세 정보 (리스트 형식)
        st.subheader("📋 실시간 상태 상세")
        cols = st.columns(3) # 학생 3명을 나란히 표시하기 위함
        
        for i, (index, row) in enumerate(df.iterrows()):
            with cols[i % 3]:
                with st.container(border=True):
                    st.write(f"**학생명: {row['student_name']}**")
                    status_color = "🔴 위험" if row['status'] == 'Red' else "🟢 정상"
                    st.write(f"상태: {status_color}")
                    if st.button(f"{row['student_name']} 위치 추적", key=f"btn_{i}"):
                        st.toast(f"{row['student_name']} 학생의 정밀 추적을 시작합니다.")
    else:
        st.warning("표시할 학생 데이터가 없습니다. Supabase 테이블을 확인해 주세요.")

# 7. 메인 로직 (로그인 여부에 따라 화면 전환)
if not st.session_state['logged_in']:
    show_login_page()
else:
    # 로그인 성공 시 레이아웃을 넓게 변경
    st.set_page_config(layout="wide") # 이 줄은 함수 내에서 작동 안 할 수 있어 상단 설정이 우선됨
    show_main_dashboard()