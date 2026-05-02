import streamlit as st
from supabase import create_client
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime

# 1. 페이지 설정
st.set_page_config(page_title="Eye-Link", layout="wide")

# 2. 세션 상태 초기화
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None
if 'selected_student_id' not in st.session_state:
    st.session_state['selected_student_id'] = None

class EyeLinkApp:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
        except:
            st.error("수파베이스 설정을 확인해주세요.")

    # --- [수파베이스 실제 테이블 연동 로그인] ---
    def login(self, email, password):
        try:
            # 선생님께서 수파베이스에 만든 'users' 테이블에서 계정 확인
            # 테이블명이나 컬럼명이 다르면 해당 부분만 수정하시면 됩니다.
            res = self.client.table("users")\
                .select("email, password, school_id, school_name")\
                .eq("email", email)\
                .eq("password", password)\
                .execute()
            
            if len(res.data) > 0:
                user_data = res.data[0]
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = {
                    "school_id": user_data['school_id'],
                    "school_name": user_data['school_name']
                }
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 일치하지 않습니다.")
        except Exception as e:
            st.error(f"로그인 오류: {e}")

    # --- [데이터 로드 로직] ---
    def fetch_students(self, school_id):
        # 수파베이스 students 테이블에서 해당 학교 학생만 호출
        res = self.client.table("students").select("*").eq("school_id", school_id).execute()
        return pd.DataFrame(res.data)

    def fetch_location_logs(self, student_id):
        # 10초 단위 기록용 location_logs 테이블 호출
        res = self.client.table("location_logs").select("created_at, lat, lon")\
            .eq("student_id", student_id).order("created_at", desc=True).limit(50).execute()
        df = pd.DataFrame(res.data)
        if not df.empty:
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%H:%M:%S')
            df.columns = ['시간', '위도', '경도']
        return df

    # --- [화면 구성] ---
    def show_login_page(self):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("👁️ Eye-Link 로그인")
            email = st.text_input("아이디(Email)")
            password = st.text_input("비밀번호", type="password")
            if st.button("로그인", use_container_width=True):
                self.login(email, password)

    def show_dashboard(self):
        user = st.session_state['user_info']
        
        # 상단바 및 로그아웃
        col_t1, col_t2 = st.columns([8, 1])
        with col_t1:
            st.title(f"🛡️ {user['school_name']} 안전 대시보드")
        with col_t2:
            if st.button("로그아웃"):
                st.session_state['logged_in'] = False
                st.rerun()
        
        st.write("---")

        # 메인 레이아웃: 왼쪽(학생 명단) | 오른쪽(지도)
        col_left, col_right = st.columns([1, 3])

        with col_left:
            st.subheader("👤 학생 명단")
            df_students = self.fetch_students(user['school_id'])
            if not df_students.empty:
                for _, row in df_students.iterrows():
                    # 수파베이스 학생 데이터를 기반으로 버튼 생성
                    if st.button(f"📍 {row['student_name']}", key=f"btn_{row['student_id']}", use_container_width=True):
                        st.session_state['selected_student_id'] = row['student_id']
                        st.session_state['selected_student_name'] = row['student_name']
                        st.rerun()
            else:
                st.info("등록된 학생 정보가 없습니다.")

        with col_right:
            self.render_kakao_map(df_students)

        # 하단 로그 섹션
        if st.session_state['selected_student_id']:
            st.write("---")
            st.subheader(f"📊 {st.session_state['selected_student_name']} 학생 상세 이동 로그 (10초 단위)")
            logs_df = self.fetch_location_logs(st.session_state['selected_student_id'])
            if not logs_df.empty:
                st.dataframe(logs_df, use_container_width=True, height=300)
            else:
                st.warning("기록된 이동 이력이 없습니다.")

    def render_kakao_map(self, df):
        if df.empty: return
        lat, lon = df.iloc[0]['lat'], df.iloc[0]['lon']
        kakao_key = st.secrets['kakao']['js_key']
        markers_js = ""
        for _, r in df.iterrows():
            markers_js += f"new kakao.maps.Marker({{map:map, position:new kakao.maps.LatLng({r['lat']},{r['lon']}), title:'{r['student_name']}'}});"

        map_html = f"""
        <html>
        <head><meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests"></head>
        <body style="margin:0;"><div id="map" style="width:100%;height:650px;border-radius:15px;"></div>
        <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
        <script>
            function init() {{
                if (typeof kakao === 'undefined' || !kakao.maps) {{ setTimeout(init, 100); return; }}
                kakao.maps.load(function() {{
                    var map = new kakao.maps.Map(document.getElementById('map'), {{center: new kakao.maps.LatLng({lat}, {lon}), level: 3}});
                    {markers_js}
                }});
            }}
            init();
        </script></body></html>
        """
        components.html(map_html, height=660)

# 실행부
if __name__ == "__main__":
    app = EyeLinkApp()
    if not st.session_state['logged_in']:
        app.show_login_page()
    else:
        app.show_dashboard()