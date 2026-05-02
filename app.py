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
if 'selected_student_name' not in st.session_state:
    st.session_state['selected_student_name'] = None
if 'show_register' not in st.session_state:
    st.session_state['show_register'] = False

class EyeLinkApp:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
        except:
            st.error("수파베이스 설정(secrets)을 확인해주세요.")

    # --- [사용자 관리 로직] ---
    def register_school(self, school_id, password, school_name, address):
        try:
            data = {"school_id": school_id, "password": password, "school_name": school_name, "address": address}
            res = self.client.table("user").insert(data).execute()
            if res.data:
                st.success("학교 등록 성공! 로그인해 주세요.")
                st.session_state['show_register'] = False
                st.rerun()
        except Exception as e:
            st.error(f"등록 실패: {e}")

    def login(self, school_id, password):
        try:
            res = self.client.table("user").select("*").eq("school_id", school_id).eq("password", password).execute()
            if len(res.data) > 0:
                st.session_state['logged_in'] = True
                st.session_state['user_info'] = res.data[0]
                st.rerun()
            else:
                st.error("학교 코드 또는 비밀번호가 틀렸습니다.")
        except:
            st.error("로그인 중 오류가 발생했습니다.")

    # --- [데이터 로직: 이미지 구조 100% 반영] ---
    def fetch_students(self, school_id):
        # students 테이블: id, student_name, lat, lon, status, school_id
        res = self.client.table("students").select("*").eq("school_id", school_id).execute()
        return pd.DataFrame(res.data)

    def fetch_location_logs(self, student_id):
        # location_logs 테이블: id, student_id(text), student_name, lat, lon, created_at(timestamptz)
        # student_id가 text 타입이므로 문자열로 비교합니다.
        res = self.client.table("location_logs")\
            .select("created_at, lat, lon")\
            .eq("student_id", str(student_id))\
            .order("created_at", desc=True)\
            .limit(50)\
            .execute()
        
        df = pd.DataFrame(res.data)
        if not df.empty:
            # 한국 시간 변환 및 포맷팅
            df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%m-%d %H:%M:%S')
            df.columns = ['기록 시간', '위도(Lat)', '경도(Lon)']
        return df

    # --- [화면 구성] ---
    def show_login_page(self):
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.session_state['show_register']:
                st.title("🏫 학교 등록")
                sid = st.text_input("학교 코드 (school_id)")
                pw = st.text_input("비밀번호", type="password")
                sname = st.text_input("학교 이름")
                addr = st.text_input("학교 주소")
                if st.button("등록 완료", use_container_width=True):
                    self.register_school(sid, pw, sname, addr)
                if st.button("돌아가기"):
                    st.session_state['show_register'] = False
                    st.rerun()
            else:
                st.title("👁️ Eye-Link 로그인")
                sid = st.text_input("학교 코드(ID)")
                pw = st.text_input("비밀번호", type="password")
                if st.button("로그인", use_container_width=True):
                    self.login(sid, pw)
                st.write("---")
                if st.button("처음이신가요? 학교 등록하기"):
                    st.session_state['show_register'] = True
                    st.rerun()

    def show_dashboard(self):
        user = st.session_state['user_info']
        col_h1, col_h2 = st.columns([9, 1])
        with col_h1:
            st.title(f"🛡️ {user['school_name']} 안전 대시보드")
        with col_h2:
            if st.button("로그아웃"):
                st.session_state['logged_in'] = False
                st.rerun()
        
        st.write("---")
        c_left, c_right = st.columns([1, 3])

        with c_left:
            st.subheader("👤 학생 명단")
            df_s = self.fetch_students(user['school_id'])
            if not df_s.empty:
                for _, r in df_s.iterrows():
                    # status 컬럼을 활용한 상태 표시
                    status_icon = "🟢" if r['status'] == "정상" else "🔴"
                    if st.button(f"{status_icon} {r['student_name']}", key=f"s_{r['id']}", use_container_width=True):
                        # location_logs 조회를 위해 student_id(text)를 세션에 저장
                        # 만약 logs 테이블의 student_id와 students 테이블의 id가 같은 값이면 r['id']를 사용
                        st.session_state['selected_student_id'] = r['id'] 
                        st.session_state['selected_student_name'] = r['student_name']
                        st.rerun()
            else:
                st.info("등록된 학생이 없습니다.")

        with c_right:
            self.render_kakao_map(df_s)

        # 하단 상세 로그 섹션
        if st.session_state['selected_student_id']:
            st.write("---")
            st.subheader(f"📊 {st.session_state['selected_student_name']} 학생 상세 이동 로그 (10초 단위)")
            l_df = self.fetch_location_logs(st.session_state['selected_student_id'])
            if not l_df.empty:
                st.dataframe(l_df, use_container_width=True, height=350)
            else:
                st.warning("기록된 위치 로그가 없습니다.")

    def render_kakao_map(self, df):
        if df.empty: return
        lat, lon = df.iloc[0]['lat'], df.iloc[0]['lon']
        k_key = st.secrets['kakao']['js_key']
        m_js = ""
        for _, r in df.iterrows():
            m_js += f"new kakao.maps.Marker({{map:map, position:new kakao.maps.LatLng({r['lat']},{r['lon']}), title:'{r['student_name']}'}});"

        m_html = f"""
        <html>
        <head>
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
            <style>body, html, #map {{width:100%; height:100%; margin:0; padding:0; border-radius:15px;}}</style>
        </head>
        <body>
            <div id="map"></div>
            <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={k_key}&autoload=false"></script>
            <script>
                function init() {{
                    if (typeof kakao === 'undefined' || !kakao.maps) {{ setTimeout(init, 100); return; }}
                    kakao.maps.load(function() {{
                        var map = new kakao.maps.Map(document.getElementById('map'), {{
                            center: new kakao.maps.LatLng({lat}, {lon}), level: 3
                        }});
                        {m_js}
                    }});
                }}
                init();
            </script>
        </body>
        </html>
        """
        components.html(m_html, height=650)

if __name__ == "__main__":
    app = EyeLinkApp()
    if not st.session_state['logged_in']:
        app.show_login_page()
    else:
        app.show_dashboard()