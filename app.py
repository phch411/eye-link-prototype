import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests
import streamlit.components.v1 as components
from datetime import datetime

# [필수] 1순위: 페이지 설정
st.set_page_config(page_title="Eye-Link", layout="wide")

# --- 1. 데이터베이스 관리 클래스 (Model) ---
class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
            self.neis_key = st.secrets["neis"]["api_key"]
        except Exception as e:
            st.error("설정 오류: Streamlit Secrets를 확인해주세요.")

    def get_school_list(self, keyword):
        """나이스 API 학교 검색"""
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {"KEY": self.neis_key, "Type": "json", "pIndex": 1, "pSize": 10, "SCHUL_NM": keyword}
        try:
            res = requests.get(url, params=params).json()
            if "schoolInfo" in res:
                return res["schoolInfo"][1]["row"]
            return []
        except: return []

    def authenticate(self, u_id, pw):
        """user 테이블에서 인증"""
        try:
            q = self.client.table("user").select("*").eq("school_id", u_id).eq("password", pw).execute()
            return q.data
        except: return []

    def register(self, u_id, pw, name, addr):
        """회원가입 실행 (user 테이블)"""
        try:
            check = self.client.table("user").select("school_id").eq("school_id", u_id).execute()
            if len(check.data) > 0: return False, "이미 존재하는 아이디입니다."
            data = {"school_id": u_id, "password": pw, "school_name": name, "address": addr}
            self.client.table("user").insert(data).execute()
            return True, "회원가입이 완료되었습니다!"
        except Exception as e: return False, f"DB 오류: {str(e)}"

    def fetch_students(self, school_id):
        """students 테이블에서 목록 가져오기"""
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

    def fetch_location_logs(self, student_id):
        """location_logs 테이블에서 특정 학생의 10초 단위 로그 가져오기"""
        try:
            res = self.client.table("location_logs")\
                .select("created_at, lat, lon")\
                .eq("student_id", str(student_id))\
                .order("created_at", desc=True)\
                .limit(50)\
                .execute()
            df = pd.DataFrame(res.data)
            if not df.empty:
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%H:%M:%S')
                df.columns = ['기록 시간', '위도(Lat)', '경도(Lon)']
            return df
        except: return pd.DataFrame()

# --- 2. UI 및 로직 제어 클래스 (View/Controller) ---
class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'show_signup' not in st.session_state: st.session_state['show_signup'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None
        if 'selected_student_id' not in st.session_state: st.session_state['selected_student_id'] = None
        if 'selected_student_name' not in st.session_state: st.session_state['selected_student_name'] = None

    def validate_pw(self, pw):
        if not pw: return None, ""
        reg = r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,}$"
        if re.match(reg, pw): return True, "✅ 안전한 비밀번호입니다."
        return False, "❌ 8자 이상, 영문+숫자+특수문자 필수"

    def show_login_page(self):
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.title("🛡️ Eye-Link")
            st.markdown("### **아이들의 발걸음이 언제나 안녕하기를.**")
            with st.container(border=True):
                u_id = st.text_input("학교 아이디 (school_id)", placeholder="아이디를 입력하세요")
                u_pw = st.text_input("비밀번호 (password)", type="password")
                if st.button("함께하기", use_container_width=True):
                    user = self.db.authenticate(u_id, u_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user[0]
                        st.rerun()
                    else: st.error("정보를 다시 확인해 주세요.")
                st.write("---")
                if st.button("우리 학교 등록하기", use_container_width=True):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_signup_page(self):
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.title("📝 학교 가입")
            with st.container(border=True):
                s_input = st.text_input("1. 학교명 검색")
                selected_school = None
                if len(s_input) >= 2:
                    school_list = self.db.get_school_list(s_input)
                    if school_list:
                        opts = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in school_list}
                        choice = st.selectbox("2. 학교 선택", options=["선택하세요"] + list(opts.keys()))
                        if choice != "선택하세요": selected_school = opts[choice]
                
                if selected_school:
                    u_id = st.text_input("3. 사용할 ID")
                    pw = st.text_input("4. 비밀번호", type="password")
                    is_v, msg = self.validate_pw(pw)
                    if pw:
                        if is_v: st.success(msg)
                        else: st.error(msg)
                    if st.button("가입 완료", use_container_width=True):
                        if u_id and is_v:
                            ok, res = self.db.register(u_id, pw, selected_school['SCHUL_NM'], selected_school['ORG_RDNMA'])
                            if ok:
                                st.success(res)
                                st.session_state['show_signup'] = False
                                st.rerun()
            if st.button("돌아가기"):
                st.session_state['show_signup'] = False
                st.rerun()

    def show_dashboard(self):
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        menu = st.sidebar.radio("관리 메뉴", ["실시간 학생 모니터링", "학생별 상황", "사전 위험구간 설정"])
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        df_students = self.db.fetch_students(user['school_id'])

        if menu == "실시간 학생 모니터링":
            st.title("👁️ 실시간 학생 모니터링")
            if not df_students.empty:
                col_list, col_map = st.columns([1, 3])
                with col_list:
                    st.subheader("👤 명단")
                    for _, row in df_students.iterrows():
                        status_icon = "🟢" if row.get('status') == "정상" else "🔴"
                        if st.button(f"{status_icon} {row['student_name']}", key=f"btn_{row['id']}", use_container_width=True):
                            st.session_state['selected_student_id'] = row['id']
                            st.session_state['selected_student_name'] = row['student_name']
                            st.rerun()
                
                with col_map:
                    logs_df = pd.DataFrame()
                    if st.session_state['selected_student_id']:
                        logs_df = self.db.fetch_location_logs(st.session_state['selected_student_id'])
                        st.info(f"📍 {st.session_state['selected_student_name']} 학생의 동선을 표시 중입니다.")
                    self.render_kakao_map(df_students, logs_df)
                
                if not logs_df.empty:
                    st.divider()
                    st.subheader(f"📊 {st.session_state['selected_student_name']} 학생 상세 기록")
                    st.dataframe(logs_df, use_container_width=True, height=250)
            else:
                st.info("데이터가 없습니다. GPS 기기를 확인해 주세요.")

    def render_kakao_map(self, df_students, logs_df=pd.DataFrame()):
        if df_students.empty: return
        
        if not logs_df.empty:
            lat, lon = logs_df.iloc[0]['위도(Lat)'], logs_df.iloc[0]['경도(Lon)']
        else:
            lat, lon = df_students.iloc[0]['lat'], df_students.iloc[0]['lon']

        kakao_key = st.secrets['kakao']['js_key']
        markers_js = ""
        for _, r in df_students.iterrows():
            markers_js += f"new kakao.maps.Marker({{map:map, position:new kakao.maps.LatLng({r['lat']},{r['lon']}), title:'{r['student_name']}'}});"

        path_js = ""
        if not logs_df.empty:
            for _, r in logs_df.iterrows():
                path_js += f"""
                new kakao.maps.Circle({{
                    map: map,
                    center: new kakao.maps.LatLng({r['위도(Lat)']}, {r['경도(Lon)']}),
                    radius: 3, strokeWeight: 1, strokeColor: '#FF0000', strokeOpacity: 0.8,
                    fillColor: '#FF0000', fillOpacity: 0.5
                }});
                """

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
                    {markers_js} {path_js}
                }});
            }}
            init();
        </script></body></html>
        """
        components.html(map_html, height=670)

if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state['logged_in']: app.show_dashboard()
    elif st.session_state['show_signup']: app.show_signup_page()
    else: app.show_login_page()