import streamlit as st
from supabase import create_client
import pandas as pd
import streamlit.components.v1 as components

# 1. 페이지 설정
st.set_page_config(page_title="Eye-Link", layout="wide")

class EyeLinkDB:
    def __init__(self):
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
        except:
            st.error("Secrets 설정을 확인해주세요.")

    def authenticate(self, u_id, pw):
        """[수정] .ilike()를 사용하여 공백이나 대소문자 차이로 인한 로그인 실패 방지"""
        try:
            # .eq() 대신 .ilike()를 사용하면 좀 더 유연하게 매칭됩니다.
            res = self.client.table("users").select("*").ilike("school_id", u_id.strip()).execute()
            if res.data:
                user = res.data[0]
                # 비밀번호도 공백을 제거하고 비교
                if str(user['password']).strip() == str(pw).strip():
                    return [user]
            return []
        except Exception as e:
            st.error(f"로그인 오류: {e}")
            return []

    def fetch_students(self, school_id):
        try:
            res = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(res.data)
        except: return pd.DataFrame()

    def fetch_location_logs(self, student_id):
        try:
            res = self.client.table("location_logs").select("created_at, lat, lon")\
                .eq("student_id", str(student_id)).order("created_at", desc=True).limit(50).execute()
            df = pd.DataFrame(res.data)
            if not df.empty:
                df.columns = ['시간', '위도', '경도']
            return df
        except: return pd.DataFrame()

class EyeLinkApp:
    def __init__(self):
        self.db = EyeLinkDB()
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None
        if 'selected_student_id' not in st.session_state: st.session_state['selected_student_id'] = None

    def show_login_page(self):
        _, col, _ = st.columns([1, 1.5, 1])
        with col:
            st.title("🛡️ Eye-Link 로그인")
            u_id = st.text_input("아이디 (school_id)")
            u_pw = st.text_input("비밀번호", type="password")
            if st.button("로그인", use_container_width=True):
                user = self.db.authenticate(u_id, u_pw)
                if user:
                    st.session_state['logged_in'] = True
                    st.session_state['user_info'] = user[0]
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 일치하지 않습니다.")

    def show_dashboard(self):
        user = st.session_state['user_info']
        st.sidebar.title(f"🏫 {user['school_name']}")
        if st.sidebar.button("로그아웃"):
            st.session_state['logged_in'] = False
            st.rerun()

        df_students = self.db.fetch_students(user['school_id'])
        st.title("👁️ 실시간 학생 모니터링")
        
        c1, c2 = st.columns([1, 3])
        with c1:
            st.subheader("👤 학생 명단")
            for _, row in df_students.iterrows():
                if st.button(f"📍 {row['student_name']}", key=f"s_{row['id']}", use_container_width=True):
                    st.session_state['selected_student_id'] = row['id']
                    st.rerun()

        with c2:
            logs_df = pd.DataFrame()
            if st.session_state['selected_student_id']:
                logs_df = self.db.fetch_location_logs(st.session_state['selected_student_id'])
            self.render_kakao_map(df_students, logs_df)

    def render_kakao_map(self, df_students, logs_df):
        if df_students.empty: return
        lat, lon = (logs_df.iloc[0]['위도'], logs_df.iloc[0]['경도']) if not logs_df.empty else (df_students.iloc[0]['lat'], df_students.iloc[0]['lon'])
        
        kakao_key = st.secrets['kakao']['js_key']
        
        # 선택 안 된 학생들 마커
        others = ""
        for _, r in df_students.iterrows():
            if str(r['id']) != str(st.session_state.get('selected_student_id')):
                others += f"new kakao.maps.Marker({{map:map, position:new kakao.maps.LatLng({r['lat']},{r['lon']})}});"

        # 선택 학생 동선 및 깜빡이는 빨간 원
        path_js, blink_js = "", ""
        if not logs_df.empty:
            for i, r in logs_df.iterrows():
                if i == 0:
                    blink_js = f"""
                    var content = '<div class="pulse-marker"></div>';
                    new kakao.maps.CustomOverlay({{position:new kakao.maps.LatLng({r['위도']},{r['경도']}), content:content, map:map}});
                    """
                else:
                    path_js += f"new kakao.maps.Circle({{map:map, center:new kakao.maps.LatLng({r['위도']},{r['경도']}), radius:3, fillOpacity:{max(0.1, 1-(i*0.05))}, fillColor:'#FF0000', strokeWeight:0}});"

        map_html = f"""
        <html>
        <head>
            <style>
                #map {{ width:100%; height:650px; border-radius:15px; }}
                .pulse-marker {{
                    width:18px; height:18px; background:#FF0000; border:3px solid #FFF; border-radius:50%;
                    box-shadow: 0 0 10px rgba(255,0,0,0.7); animation: pulse 1.5s infinite;
                }}
                @keyframes pulse {{
                    0% {{ transform:scale(0.9); box-shadow:0 0 0 0 rgba(255,0,0,0.7); }}
                    70% {{ transform:scale(1.1); box-shadow:0 0 0 15px rgba(255,0,0,0); }}
                    100% {{ transform:scale(0.9); box-shadow:0 0 0 0 rgba(255,0,0,0); }}
                }}
            </style>
        </head>
        <body>
            <div id="map"></div>
            <script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                function init() {{
                    kakao.maps.load(function() {{
                        var map = new kakao.maps.Map(document.getElementById('map'), {{center:new kakao.maps.LatLng({lat},{lon}), level:3}});
                        {others} {path_js} {blink_js}
                    }});
                }}
                setTimeout(init, 100);
            </script>
        </body>
        </html>
        """
        components.html(map_html, height=670)

if __name__ == "__main__":
    app = EyeLinkApp()
    if st.session_state.get('logged_in'): app.show_dashboard()
    else: app.show_login_page()