import streamlit as st
from supabase import create_client
import pandas as pd

# 1. 데이터베이스 관리 클래스
class EyeLinkDB:
    def __init__(self):
        self.url = st.secrets["supabase"]["url"]
        self.key = st.secrets["supabase"]["key"]
        self.client = create_client(self.url, self.key)

    def authenticate_user(self, school_id, password):
        """사용자 인증 로직"""
        try:
            query = self.client.table("users")\
                .select("*")\
                .eq("school_id", school_id)\
                .eq("password", password)\
                .execute()
            return query.data
        except Exception as e:
            st.error(f"인증 오류: {e}")
            return []

    def fetch_students(self):
        """학생 데이터 호출 로직"""
        try:
            query = self.client.table("students").select("*").execute()
            return pd.DataFrame(query.data)
        except Exception as e:
            st.error(f"데이터 로드 오류: {e}")
            return pd.DataFrame()

# 2. UI 및 앱 흐름 제어 클래스
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        self._initialize_session()

    def _initialize_session(self):
        """세션 상태 초기화"""
        if 'logged_in' not in st.session_state:
            st.session_state['logged_in'] = False
        if 'school_name' not in st.session_state:
            st.session_state['school_name'] = ""

    def run(self):
        """앱 실행 메인 로직"""
        if not st.session_state['logged_in']:
            self.show_login_page()
        else:
            self.show_main_dashboard()

    def show_login_page(self):
        """중앙 집중형 로그인 화면"""
        st.set_page_config(page_title="Eye-Link 로그인", layout="centered")
        _, col2, _ = st.columns([1, 2, 1])
        
        with col2:
            st.write("")
            st.title("🛡️ Eye-Link")
            st.subheader("학교 관리자 로그인")
            
            with st.container(border=True):
                s_id = st.text_input("학교 식별 코드")
                s_pw = st.text_input("비밀번호", type="password")
                if st.button("시스템 접속", use_container_width=True):
                    user_data = self.db.authenticate_user(s_id, s_pw)
                    if user_data:
                        st.session_state['logged_in'] = True
                        st.session_state['school_name'] = user_data[0]['school_name']
                        st.rerun()
                    else:
                        st.error("아이디 또는 비밀번호가 일치하지 않습니다.")

    def show_main_dashboard(self):
        """메인 관제 대시보드"""
        st.set_page_config(page_title="Eye-Link 대시보드", layout="wide")
        
        # 사이드바 설정
        st.sidebar.title(f"🏫 {st.session_state['school_name']}")
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        st.title("👁️ 실시간 학생 안전 모니터링")
        
        df = self.db.fetch_students()

        if not df.empty:
            # MVP 1: 위험 알림
            danger_students = df[df['status'] == 'Red']
            if not danger_students.empty:
                st.error(f"🚨 경고: {len(danger_students)}명의 학생이 위험 구역에 있거나 이탈했습니다!")

            # MVP 2: 실시간 맵
            st.subheader("📍 학생 실시간 위치 현황")
            st.map(df)

            # 상세 정보 카드
            st.subheader("📋 학생 상태 상세 리포트")
            cols = st.columns(len(df) if len(df) > 0 else 1)
            for i, (idx, row) in enumerate(df.iterrows()):
                with cols[i]:
                    with st.container(border=True):
                        st.write(f"**이름: {row['student_name']}**")
                        color = "🔴" if row['status'] == 'Red' else "🟢"
                        st.write(f"상태: {color} {row['status']}")
        else:
            st.warning("등록된 학생 데이터가 없습니다.")

# 3. 실제 앱 실행
if __name__ == "__main__":
    app = EyeLinkApp()
    app.run()