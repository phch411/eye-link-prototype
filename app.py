import streamlit as st
from supabase import create_client
import pandas as pd
import re
import requests
import streamlit.components.v1 as components
from datetime import datetime

# 1. 페이지 설정
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
            st.error("설정 오류: Secrets를 확인해주세요.")

    def authenticate(self, u_id, pw):
        try:
            res = self.client.table("users").select("*").eq("school_id", u_id.strip()).execute()
            if res.data:
                user = res.data[0]
                if str(user['password']).strip() == str(pw).strip():
                    return [user]
            return []
        except: return []

    def get_school_list(self, keyword):
        url = "https://open.neis.go.kr/hub/schoolInfo"
        params = {"KEY": self.neis_key, "Type": "json", "pIndex": 1, "pSize": 10, "SCHUL_NM": keyword}
        try:
            res = requests.get(url, params=params).json()
            if "schoolInfo" in res: return res["schoolInfo"][1]["row"]
            return []
        except: return []

    def register(self, u_id, pw, name, addr):
        try:
            check = self.client.table("users").select("school_id").eq("school_id", u_id).execute()
            if len(check.data) > 0: return False, "이미 존재하는 아이디입니다."
            data = {"school_id": u_id, "password": pw, "school_name": name, "address": addr}
            self.client.table("users").insert(data).execute()
            return True, "회원가입 완료!"
        except: return False, "DB 오류"

    def fetch_students(self, school_id):
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).order("student_name").execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

    def fetch_location_logs(self, student_id):
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

    def show_login_page(self):
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.title("🛡️ Eye-Link")
            with st.container(border=True):
                u_id = st.text_input("아이디 (school_id)")
                u_pw = st.text_input("비밀번호", type="password")
                if st.button("함께하기", use_container_width=True):
                    user = self.db.authenticate(u_id, u_pw)
                    if user:
                        st.session_state['logged_in'] = True
                        st.session_state['user_info'] = user[0]
                        st.rerun()
                    else: st.error("정보를 확인해주세요.")
                st.write("---")
                if st.button("우리 학교 등록하기", use_container_width=True):
                    st.session_state['show_signup'] = True
                    st.rerun()

    def show_signup_page(self):
        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.title("📝 학교 가입")
            s_input = st.text_input("학교명 검색")
            if len(s_input) >= 2:
                s_list = self.db.get_school_list(s_input)
                if s_list:
                    opts = {f"{s['SCHUL_NM']} ({s['ORG_RDNMA']})": s for s in s_list}
                    choice = st.selectbox("학교 선택", options=["선택하세요"] + list(opts.keys()))
                    if choice != "선택하세요":
                        sel = opts[choice]
                        u_id = st.text_input("사용할 ID")
                        pw = st.text_input("비밀번호", type="password")
                        if st.button("가입 완료"):
                            ok, msg = self.db.register(u_id, pw, sel['SCHUL_NM'], sel['ORG_RDNMA'])
                            if ok: st.success(msg); st.session_state['show_signup'] = False; st.rerun()
            if st.button("돌아가기"): st.session_state['show_signup'] = False; st.rerun()

    def show_dashboard(self):
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        
        df_students = self.db.fetch_students(user['school_id'])
        
        menu = st.sidebar.radio("관리 메뉴", ["실시간 학생 모니터링", "학생 위치 전송 시스템"])
        if st.sidebar.button("로그아웃"): st.session_state['logged_in'] = False; st.rerun()

        if menu == "실시간 학생 모니터링":
            st.title("👁️ 실시간 학생 모니터링")
            if not df_students.empty:
                c1, c2 = st.columns([1, 3])
                with c1:
                    st.subheader("👤 명단")
                    for _, row in df_students.iterrows():
                        status_icon = "🟢" if row.get('status') == "전송중" else "🔴"
                        if st.button(f"{status_icon} {row['student_name']}", key=f"s_{row['id']}", use_container_width=True):
                            st.session_state['selected_student_id'] = row['id']
                            st.session_state['selected_student_name'] = row['student_name']
                            st.rerun()
                with c2:
                    logs_df = pd.DataFrame()
                    if st.session_state.get('selected_student_id'):
                        logs_df = self.db.fetch_location_logs(st.session_state['selected_student_id'])
                    self.render_kakao_map(df_students, logs_df)
            else: st.info("데이터가 없습니다. 학생용 화면에서 전송을 시작해주세요.")

        elif menu == "학생 위치 전송 시스템":
            st.title("📲 학생 위치 전송 시스템")
            with st.container(border=True):
                s_name = st.text_input("학생 이름 입력", placeholder="이름을 입력하면 모니터링 명단에 등록됩니다.")
                if st.button("🚀 위치 전송 시작", use_container_width=True, type="primary"):
                    if s_name:
                        st.session_state['tracking_active'] = True
                        st.success(f"{s_name} 학생 전송 시작!")
                    else: st.warning("이름을 입력해주세요.")
                if st.button("⏹️ 전송 중지"): st.session_state['tracking_active'] = False; st.rerun()
                if st.session_state['tracking_active']:
                    self.render_gps_sender(s_name, user['school_id'])

    def render_gps_sender(self, s_name, school_id):
        """
        [int8 형식 맞춤 버전]
        1. ID 숫자 변환: 문자열 studentId를 Number()로 감싸 int8 형식에 맞춤
        2. 필드 명시: 수파베이스 컬럼명과 100% 일치하도록 소문자 구성
        3. 전송 확인: 성공 시 초록색 메시지 출력
        """
        url, key = st.secrets["supabase"]["url"], st.secrets["supabase"]["key"]
        gps_js = f"""
        <script>
        const sUrl = "{url}";
        const sKey = "{key}";
        const schoolId = "{school_id}";
        const sName = "{s_name}";
        
        // 고유 ID 생성 후 숫자로 변환 (int8 대응)
        const rawId = Math.abs(sName.split('').reduce((a,b)=>{{a=((a<<5)-a)+b.charCodeAt(0);return a&a}},0) % 1000000);
        const studentId = Number(rawId); 

        function updateStatus(msg, color) {{
            const el = document.getElementById('status-msg');
            if(el) {{
                el.innerText = msg;
                el.style.color = color;
            }}
        }}

        async function pushData() {{
            if (!navigator.geolocation) {{
                updateStatus("GPS 미지원 브라우저", "red");
                return;
            }}

            navigator.geolocation.getCurrentPosition(async (pos) => {{
                const lat = parseFloat(pos.coords.latitude.toFixed(6));
                const lon = parseFloat(pos.coords.longitude.toFixed(6));
                const now = new Date().toISOString();

                try {{
                    // 1. location_logs 전송 (student_id를 숫자로 전송)
                    const resLog = await fetch(sUrl + "/rest/v1/location_logs", {{
                        method: "POST",
                        headers: {{
                            "apikey": sKey,
                            "Authorization": "Bearer " + sKey,
                            "Content-Type": "application/json"
                        }},
                        body: JSON.stringify({{
                            student_id: studentId, 
                            student_name: sName,
                            lat: lat,
                            lon: lon,
                            created_at: now
                        }})
                    }});

                    // 2. students 전송 (id를 숫자로 전송)
                    const resStd = await fetch(sUrl + "/rest/v1/students", {{
                        method: "POST",
                        headers: {{
                            "apikey": sKey,
                            "Authorization": "Bearer " + sKey,
                            "Content-Type": "application/json",
                            "Prefer": "resolution=merge-duplicates"
                        }},
                        body: JSON.stringify({{
                            id: studentId,
                            student_name: sName,
                            school_id: schoolId,
                            status: "전송중",
                            lat: lat,
                            lon: lon
                        }})
                    }});

                    if(resLog.ok && resStd.ok) {{
                        updateStatus("● 실시간 데이터 기록 중 (정상)", "#2e7d32");
                    }} else {{
                        const errText = await resLog.text();
                        console.error("Error Detail:", errText);
                        updateStatus("전송 실패: " + resLog.status, "red");
                    }}
                }} catch (e) {{
                    updateStatus("네트워크 오류", "red");
                }}
            }}, (err) => {{
                updateStatus("GPS 권한 허용 필요", "orange");
            }}, {{ enableHighAccuracy: true }});
        }}

        pushData();
        setInterval(pushData, 10000);
        </script>
        <div style="text-align:center; padding:15px; background:#fff; border:2px solid #2e7d32; border-radius:10px;">
            <h4 style="margin:0; color:#2e7d32;">🛰️ {s_name} 학생 위치 전송기</h4>
            <div id="status-msg" style="font-weight:bold; margin-top:5px; font-size:0.9rem;">연결 중...</div>
        </div>
        """
        components.html(gps_js, height=120)

    def render_kakao_map(self, df_students, logs_df):
        """[안정화 버전] 지도가 완전히 로드될 때까지 기다린 후 실행"""
        if df_students.empty:
            return
            
        selected_id = st.session_state.get('selected_student_id')
        
        # 1. 중심 좌표 결정
        if not logs_df.empty:
            lat, lon = logs_df.iloc[0]['위도'], logs_df.iloc[0]['경도']
            is_active = True
        else:
            current = df_students[df_students['id'].astype(str) == str(selected_id)] if selected_id else pd.DataFrame()
            if not current.empty and current.iloc[0]['lat'] != 0:
                lat, lon = current.iloc[0]['lat'], current.iloc[0]['lon']
                is_active = False
            else:
                st.info("위치 기록이 아직 없습니다.")
                return

        kakao_key = st.secrets['kakao']['js_key']
        
        # 2. 마커 및 오버레이 스크립트 구성
        all_markers_js = ""
        for _, r in df_students.iterrows():
            if r['lat'] != 0 and str(r['id']) != str(selected_id):
                all_markers_js += f"new kakao.maps.Marker({{ position: new kakao.maps.LatLng({r['lat']}, {r['lon']}), map: map, title: '{r['student_name']}' }});"

        target_js = ""
        if is_active:
            target_js = f"""
            var content = '<div class="pulse-marker"></div>';
            new kakao.maps.CustomOverlay({{
                position: new kakao.maps.LatLng({lat}, {lon}),
                content: content, map: map, yAnchor: 0.5
            }});
            """
        else:
            target_js = f"new kakao.maps.Marker({{ position: new kakao.maps.LatLng({lat}, {lon}), map: map }});"

        map_html = f"""
        <html>
        <head>
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
            <style>
                #map {{ width: 100%; height: 600px; border-radius: 15px; background-color: #f8f8f8; }}
                .pulse-marker {{ width: 18px; height: 18px; background: #FF0000; border: 3px solid #FFF; border-radius: 50%; box-shadow: 0 0 10px rgba(255,0,0,0.7); animation: pulse 1.5s infinite; }}
                @keyframes pulse {{ 0% {{ transform: scale(0.95); opacity: 1; }} 70% {{ transform: scale(1.1); opacity: 0.7; }} 100% {{ transform: scale(0.95); opacity: 1; }} }}
            </style>
        </head>
        <body style="margin:0;">
            <div id="map"></div>
            <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                function initMap() {{
                    // kakao 객체가 로드될 때까지 재시도
                    if (typeof kakao === 'undefined' || !kakao.maps) {{
                        setTimeout(initMap, 100);
                        return;
                    }}
                    
                    kakao.maps.load(function() {{
                        var container = document.getElementById('map');
                        var options = {{
                            center: new kakao.maps.LatLng({lat}, {lon}),
                            level: 3
                        }};
                        var map = new kakao.maps.Map(container, options);
                        
                        {all_markers_js}
                        {target_js}
                    }});
                }}
                initMap();
            </script>
        </body>
        </html>
        """
        components.html(map_html, height=620)

# --- 3. 실행부 ---
if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state.get('logged_in'): app.show_dashboard()
    elif st.session_state.get('show_signup'): app.show_signup_page()
    else: app.show_login_page()