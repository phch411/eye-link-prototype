import streamlit as st
from supabase import create_client
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# [필수] 페이지 설정
st.set_page_config(page_title="Eye-Link", layout="wide")

class EyeLinkApp:
    def __init__(self):
        # 세션 상태 초기화
        if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
        if 'user_info' not in st.session_state: st.session_state['user_info'] = None
        if 'selected_student' not in st.session_state: st.session_state['selected_student'] = None
        
        # DB 연결 (기존 설정 유지)
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
        except: pass

    def fetch_students(self, school_id):
        try:
            q = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(q.data)
        except: return pd.DataFrame()

    def show_dashboard(self):
        user = st.session_state['user_info']
        
        # 뒤로가기 버튼 (학생 상세 보기 중일 때)
        if st.session_state['selected_student']:
            if st.button("⬅️ 전체 목록으로 돌아가기"):
                st.session_state['selected_student'] = None
                st.rerun()
            self.show_student_logs(st.session_state['selected_student'])
            return

        st.title("👁️ 실시간 학생 모니터링")
        df = self.fetch_students(user['school_id'])

        col_list, col_map = st.columns([1, 3])

        with col_list:
            st.subheader("👤 학생 명단")
            if not df.empty:
                for _, row in df.iterrows():
                    # [기능 2] 기기 연결 상태 확인 (최근 5분 이내 업데이트 기준)
                    last_update = pd.to_datetime(row.get('updated_at'))
                    is_online = (datetime.now() - last_update.replace(tzinfo=None)) < timedelta(minutes=5)
                    
                    status_color = "🟢" if is_online else "🔴"
                    status_text = "연결됨" if is_online else "연결 끊김"
                    
                    # [기능 3] 학생 이름 클릭 시 상세 페이지 이동
                    if st.button(f"{status_color} {row['student_name']}", key=row['student_name'], use_container_width=True):
                        st.session_state['selected_student'] = row.to_dict()
                        st.rerun()
                    
                    st.caption(f"상태: {status_text} (최근: {last_update.strftime('%H:%M')})")
                    st.write("")
            else:
                st.info("등록된 학생이 없습니다.")

        with col_map:
            # [기능 1] 지도의 세로 크기를 700px로 키움
            self.render_kakao_map(df, height=700)

    def show_student_logs(self, student):
        """학생별 위치 로그 상세 창"""
        st.title(f"📍 {student['student_name']} 학생 이동 로그")
        st.write(f"현재 위치: 위도 {student['lat']}, 경도 {student['lon']}")
        
        # 실제 구현 시에는 위치 기록(history) 테이블에서 데이터를 가져와 표로 보여줍니다.
        st.subheader("최근 이동 기록")
        dummy_data = {
            "시간": ["10:30", "10:35", "10:40"],
            "장소": ["학교 정문", "도서관 앞", "교실"],
            "상태": ["정상", "정상", "정상"]
        }
        st.table(pd.DataFrame(dummy_data))

    def render_kakao_map(self, df, height):
        if df.empty:
            st.warning("지도에 표시할 데이터가 없습니다.")
            return

        lat, lon = df.iloc[0]['lat'], df.iloc[0]['lon']
        kakao_key = st.secrets['kakao']['js_key']
        
        markers_js = ""
        for _, r in df.iterrows():
            markers_js += f"new kakao.maps.Marker({{map:map, position:new kakao.maps.LatLng({r['lat']},{r['lon']}), title:'{r['student_name']}'}});"

        map_html = f"""
        <html>
        <head><meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests"></head>
        <body>
            <div id="map" style="width:100%;height:{height}px;border-radius:15px;"></div>
            <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                function init() {{
                    if (typeof kakao === 'undefined' || !kakao.maps) {{ setTimeout(init, 100); return; }}
                    kakao.maps.load(function() {{
                        var map = new kakao.maps.Map(document.getElementById('map'), {{
                            center: new kakao.maps.LatLng({lat}, {lon}), level: 3
                        }});
                        {markers_js}
                    }});
                }}
                init();
            </script>
        </body>
        </html>
        """
        components.html(map_html, height=height + 20)

# --- 실행부 ---
if __name__ == "__main__":
    # 임시 로그인 세션 (테스트용)
    if not st.session_state['logged_in']:
        # 선생님 계정 정보로 자동 로그인 처리 (발표용)
        st.session_state['logged_in'] = True
        st.session_state['user_info'] = {"school_id": "bugok_hakpo", "school_name": "부곡초등학교 학포분교"}
    
    app = EyeLinkApp()
    app.show_dashboard()