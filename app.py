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
        """[해결] 테이블명을 'users'로 고정하고 공백 제거 로직 추가"""
        try:
            # 입력값의 공백을 제거하고 'users' 테이블에서 검색
            res = self.client.table("users").select("*").eq("school_id", u_id.strip()).execute()
            if res.data:
                user = res.data[0]
                # 비밀번호 비교 (공백 제거)
                if str(user['password']).strip() == str(pw).strip():
                    return [user]
            return []
        except Exception as e:
            st.error(f"로그인 오류: {e}")
            return []

    def register(self, u_id, pw, name, addr):
        """회원가입 실행 (users 테이블)"""
        try:
            check = self.client.table("users").select("school_id").eq("school_id", u_id).execute()
            if len(check.data) > 0: return False, "이미 존재하는 아이디입니다."
            data = {"school_id": u_id, "password": pw, "school_name": name, "address": addr}
            self.client.table("users").insert(data).execute()
            return True, "회원가입이 완료되었습니다!"
        except Exception as e: return False, f"DB 오류: {str(e)}"

    def fetch_students(self, school_id):
        """학생 목록 가져오기"""
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

    def fetch_location_logs(self, student_id):
        """위치 로그 가져오기"""
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
                df.columns = ['시간', '위도', '경도']
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
        if 'tracking_active' not in st.session_state: st.session_state['tracking_active'] = False

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
                u_id = st.text_input("아이디 (ID)", placeholder="학교 아이디를 입력하세요")
                u_pw = st.text_input("비밀번호", type="password")
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
                s_input = st.text_input("1. 학교명 검색 (2글자 이상 입력)")
                selected_school = None
                if len(s_input) >= 2:
                    school_list = self.db.get_school_list(s_input)
                    if school_list:
                        opts = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in school_list}
                        choice = st.selectbox("2. 학교 선택", options=["선택하세요"] + list(opts.keys()))
                        if choice != "선택하세요": selected_school = opts[choice]
                
                if selected_school:
                    st.divider()
                    st.info(f"📍 선택된 학교: {selected_school['SCHUL_NM']}")
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
                            else: st.error(res)
            if st.button("돌아가기"):
                st.session_state['show_signup'] = False
                st.rerun()

    def show_dashboard(self):
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        menu = st.sidebar.radio("관리 메뉴", ["실시간 학생 모니터링", "학생 위치 전송 시스템", "학생별 상황", "사전 위험구간 설정"])
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        if menu == "실시간 학생 모니터링":
            st.title("👁️ 실시간 학생 모니터링")
            df_s = self.db.fetch_students(user['school_id'])
            if not df_s.empty:
                c1, c2 = st.columns([1, 3])
                with c1:
                    st.subheader("👤 명단")
                    for _, row in df_s.iterrows():
                        status_icon = "🟢" if row.get('status') == "정상" else "🔴"
                        if st.button(f"{status_icon} {row['student_name']}", key=f"btn_{row['id']}", use_container_width=True):
                            st.session_state['selected_student_id'] = row['id']
                            st.session_state['selected_student_name'] = row['student_name']
                            st.rerun()
                with c2:
                    logs_df = pd.DataFrame()
                    if st.session_state.get('selected_student_id'):
                        logs_df = self.db.fetch_location_logs(st.session_state['selected_student_id'])
                    self.render_kakao_map(df_s, logs_df)
            else: st.info("등록된 학생이 없습니다.")

        elif menu == "학생 위치 전송 시스템":
            st.title("📲 학생 위치 전송 시스템")
            with st.container(border=True):
                s_name = st.text_input("학생 이름 입력", placeholder="이름을 입력하세요")
                if st.button("🚀 위치 전송 시작", use_container_width=True, type="primary"):
                    if s_name:
                        st.session_state['tracking_active'] = True
                        st.success(f"{s_name} 학생 전송 시작!")
                    else: st.warning("이름을 입력해주세요.")
                if st.button("⏹️ 전송 중지", use_container_width=True):
                    st.session_state['tracking_active'] = False
                    st.rerun()
                if st.session_state['tracking_active']:
                    self.render_gps_sender(s_name)
        else:
            st.title(f"📂 {menu}")
            st.write("준비 중인 기능입니다.")

    def render_gps_sender(self, s_name):
        s_url = st.secrets["supabase"]["url"]
        s_key = st.secrets["supabase"]["key"]
        gps_js = f"""
        <script>
        function generateId(name) {{
            const agent = window.navigator.userAgent;
            const screen = window.screen.width + "x" + window.screen.height;
            const str = name + agent + screen;
            let hash = 0;
            for (let i = 0; i < str.length; i++) {{
                hash = ((hash << 5) - hash) + str.charCodeAt(i);
                hash |= 0;
            }}
            return Math.abs(hash % 1000000).toString().padStart(6, '0');
        }}
        const autoId = generateId("{s_name}");
        function sendLoc() {{
            if (navigator.geolocation) {{
                navigator.geolocation.getCurrentPosition((pos) => {{
                    fetch("{s_url}/rest/v1/location_logs", {{
                        method: 'POST',
                        headers: {{ 'apikey': "{s_key}", 'Authorization': 'Bearer {s_key}', 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{
                            student_id: autoId, student_name: "{s_name}",
                            lat: pos.coords.latitude, lon: pos.coords.longitude,
                            created_at: new Date().toISOString()
                        }})
                    }});
                }});
            }}
        }}
        sendLoc();
        setInterval(sendLoc, 10000);
        </script>
        <div style="text-align:center; padding:10px; background:#e3f2fd; border-radius:10px;">
            <h4 style="color:#0d47a1;">🛰️ {s_name} 학생 GPS 전송 중...</h4>
        </div>
        """
        components.html(gps_js, height=100)

    def render_kakao_map(self, df_students, logs_df):
        if df_students.empty: return
        
        # 중심점 설정
        if not logs_df.empty:
            lat, lon = logs_df.iloc[0]['위도'], logs_df.iloc[0]['경도']
        else:
            lat, lon = df_students.iloc[0]['lat'], df_students.iloc[0]['lon']

        kakao_key = st.secrets['kakao']['js_key']
        
        # 일반 마커 (선택되지 않은 학생들)
        others_js = ""
        for _, r in df_students.iterrows():
            if str(r['id']) != str(st.session_state.get('selected_student_id')):
                others_js += f"new kakao.maps.Marker({{map:map, position:new kakao.maps.LatLng({r['lat']},{r['lon']})}});"

        # 동선 및 깜빡임 효과
        path_js, blink_js = "", ""
        if not logs_df.empty:
            for i, r in logs_df.iterrows():
                opacity = max(0.2, 1.0 - (i * 0.05))
                if i == 0:
                    blink_js = f"""
                    var content = '<div class="pulse-marker"></div>';
                    var overlay = new kakao.maps.CustomOverlay({{
                        position: new kakao.maps.LatLng({r['위도']}, {r['경도']}),
                        content: content, yAnchor: 0.5
                    }});
                    overlay.setMap(map);
                    """
                else:
                    path_js += f"""
                    new kakao.maps.Circle({{
                        map: map, center: new kakao.maps.LatLng({r['위도']}, {r['경도']}),
                        radius: 4, strokeWeight: 0, fillColor: '#FF0000', fillOpacity: {opacity}
                    }});
                    """

        # [수정] autoload=false 설정 및 명시적 로드 처리
        map_html = f"""
        <html>
        <head>
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
            <style>
                #map {{ width: 100%; height: 650px; border-radius: 15px; background-color: #f0f0f0; }}
                .pulse-marker {{
                    width: 18px; height: 18px; background: #FF0000; border: 3px solid #FFF; border-radius: 50%;
                    box-shadow: 0 0 10px rgba(255,0,0,0.7); animation: pulse 1.5s infinite;
                }}
                @keyframes pulse {{
                    0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.7); }}
                    70% {{ transform: scale(1.1); box-shadow: 0 0 0 15px rgba(255, 0, 0, 0); }}
                    100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }}
                }}
            </style>
        </head>
        <body style="margin:0;">
            <div id="map"></div>
            <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                // 지도가 그려지지 않을 경우를 대비해 반복 확인
                function loadMap() {{
                    if (typeof kakao === 'undefined' || !kakao.maps) {{
                        setTimeout(loadMap, 100);
                        return;
                    }}
                    
                    kakao.maps.load(function() {{
                        var container = document.getElementById('map');
                        var options = {{
                            center: new kakao.maps.LatLng({lat}, {lon}),
                            level: 3
                        }};
                        var map = new kakao.maps.Map(container, options);
                        
                        {others_js}
                        {path_js}
                        {blink_js}
                    }});
                }}
                loadMap();
            </script>
        </body>
        </html>
        """
        components.html(map_html, height=670)

# --- 3. 실행부 ---
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state.get('logged_in'): app.show_dashboard()
    elif st.session_state.get('show_signup'): app.show_signup_page()
    else: app.show_login_page()