import streamlit as st
from supabase import create_client
import pandas as pd
import numpy as np

# 1. Supabase 연결 (secrets 활용)
url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["key"]
supabase = create_client(url, key)

# 2. 데이터 불러오기 함수 (캐싱을 이용해 성능 최적화 가능)
def load_data():
    # students 테이블에서 데이터 호출
    response = supabase.table("students").select("*").execute()
    return pd.DataFrame(response.data)

# 3. 대시보드 레이아웃 설정
st.set_page_config(page_title="Eye-Link 실시간 모니터링", layout="wide")
st.title("👁️ Eye-Link: 특수아동 안전 관리 시스템")

# 자동 새로고침 설정 (선택 사항)
if st.button('데이터 갱신'):
    df = load_data()

    if not df.empty:
        # NumPy를 활용한 데이터 처리 (예: 위도/경도 배열화)
        coords = df[['lat', 'lon']].to_numpy()
        
        # 상단 지표(Metric) 표시
        col1, col2, col3 = st.columns(3)
        col1.metric("총 인원", f"{len(df)}명")
        col2.metric("위험(Red)", f"{len(df[df['status'] == 'Red'])}명")
        col3.metric("정상(Green)", f"{len(df[df['status'] == 'Green'])}명")

        # 4. 지도 시각화 (Streamlit 기본 지도)
        st.subheader("📍 학생 실시간 위치 현황")
        st.map(df) # df 안에 'lat', 'lon' 컬럼이 있으면 자동 인식

        # 5. 상세 데이터 테이블
        st.subheader("📋 실시간 상태 리스트")
        st.dataframe(df.style.applymap(
            lambda x: 'background-color: #ffcccc' if x == 'Red' else ('background-color: #ccffcc' if x == 'Green' else ''),
            subset=['status']
        ))
    else:
        st.warning("현재 데이터베이스에 학생 데이터가 없습니다.")

# 로그인 상태 관리 (세션 스테이트 활용)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

def login():
    st.sidebar.title("🏫 학교 로그인")
    school_id = st.sidebar.text_input("학교 ID")
    password = st.sidebar.text_input("비밀번호", type="password")
    
    if st.sidebar.button("로그인"):
        # MVP 단계이므로 간단한 ID/PW 확인 (추후 DB 연동 가능)
        if school_id == "admin" and password == "1234":
            st.session_state['logged_in'] = True
            st.rerun()
        else:
            st.sidebar.error("ID 또는 비밀번호가 일치하지 않습니다.")

# 로그인 여부에 따른 화면 제어
if not st.session_state['logged_in']:
    st.title("🛡️ Eye-Link 시스템")
    st.info("왼쪽 사이드바에서 학교 로그인을 진행해 주세요.")
    login()
else:
    # --- 여기서부터 기존 대시보드 코드 ---
    st.sidebar.success("로그인 성공!")
    if st.sidebar.button("로그아웃"):
        st.session_state['logged_in'] = False
        st.rerun()
    
    # (이전의 지도 및 데이터 불러오기 코드 입력)
    st.title("👁️ Eye-Link: 실시간 모니터링")