import streamlit as st
from supabase import create_client
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# 1. 페이지 설정 (가장 먼저 실행되어야 함)
st.set_page_config(page_title="Eye-Link", layout="wide")

# 2. 세션 상태 초기화 (KeyError 방지)
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = True  # 발표용 자동 로그인
if 'user_info' not in st.session_state:
    # 선생님의 부곡초 학포분교 설정
    st.session_state['user_info'] = {"school_id": "bugok_hakpo", "school_name": "부곡초등학교 학포분교"}
if 'selected_student_id' not in st.session_state:
    st.session_state['selected_student_id'] = None
if 'selected_student_name' not in st.session_state:
    st.session_state['selected_student_name'] = None

class EyeLinkApp:
    def __init__(self):
        # 수파베이스 연결
        try:
            self.url = st.secrets["supabase"]["url"]
            self.key = st.secrets["supabase"]["key"]
            self.client = create_client(self.url, self.key)
        except Exception as e:
            st.error(f"수파베이스 연결 실패: {e}")

    def fetch_students(self, school_id):
        """학생 목록 가져오기 (지도 마커용 및 명단용)"""
        try:
            res = self.client.table("students").select("*").eq("school_id", school_id).execute()
            return pd.DataFrame(res.data)
        except:
            return pd.DataFrame()

    def fetch_location_logs(self, student_id):
        """수파베이스 location_logs 테이블에서 10초 단위 기록 가져오기"""
        try:
            # 10초 단위로 쌓인 로그 중 최신 50개 추출
            res = self.client.table("location_logs")\
                .select("created_at, lat, lon")\
                .eq("student_id", student_id)\
                .order("created_at", desc=True)\
                .limit(50)\
                .execute()
            
            df = pd.DataFrame(res.data)
            if not df.empty:
                # 시간 형식 보기 좋게 변환 (한국 시간 기준)
                df['created_at'] = pd.to_datetime(df['created_at']).dt.strftime('%Y-%m-%d %H:%M:%S')
                df.columns = ['기록 시간', '위도(Lat)', '경도(Lon)']
            return df
        except:
            return pd.DataFrame()

    def render_kakao_map(self, df, height):
        """카카오맵 렌더링 (보안 정책 및 로딩 지연 해결 버전)"""
        if df.empty:
            st.info("지도에 표시할 위치 정보가 없습니다.")
            return

        # 지도 중심점 설정 (첫 번째 학생 기준)
        center_lat, center_lon = df.iloc[0]['lat'], df.iloc[0]['lon']
        kakao_key = st.secrets['kakao']['js_key']
        
        # 마커 생성 스크립트
        markers_js = ""
        for _, r in df.iterrows():
            markers_js += f"""
                new kakao.maps.Marker({{
                    map: map,
                    position: new kakao.maps.LatLng({r['lat']}, {r['lon']}),
                    title: '{r['student_name']}'
                }});
            """

        map_html = f"""
        <html>
        <head>
            <meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">
            <style>body, html, #map {{width:100%; height:100%; margin:0; padding:0; border-radius:15px;}}</style>
        </head>
        <body>
            <div id="map"></div>
            <script type="text/javascript" src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={kakao_key}&autoload=false"></script>
            <script>
                function initMap() {{
                    if (typeof kakao === 'undefined' || !kakao.maps) {{
                        setTimeout(initMap, 100);
                        return;
                    }}
                    kakao.maps.load(function() {{
                        var container = document.getElementById('map');
                        var options = {{
                            center: new kakao.maps.LatLng({center_lat}, {center_lon}),
                            level: 3
                        }};
                        var map = new kakao.maps.Map(container, options);
                        {markers_js}
                    }});
                }}
                initMap();
            </script>
        </body>
        </html>
        """
        components.html(map_html, height=height)

    def show_dashboard(self):
        user = st.session_state['user_info']
        
        st.title(f"👁️ Eye-Link: {user['school_name']} 모니터링")
        st.write("---")

        # 메인 레이아웃: 왼쪽(학생 명단) | 오른쪽(지도)
        col_list, col_map = st.columns([1, 3])

        with col_list:
            st.subheader("👤 학생 명단")
            df_students = self.fetch_students(user['school_id'])
            
            if not df_students.empty:
                for _, row in df_students.iterrows():
                    # 버튼 클릭 시 해당 학생의 로그를 불러오도록 상태 변경
                    if st.button(f"📍 {row['student_name']}", key=f"btn_{row['student_id']}", use_container_width=True):
                        st.session_state['selected_student_id'] = row['student_id']
                        st.session_state['selected_student_name'] = row['student_name']
                        st.rerun()
            else:
                st.info("학생 데이터가 없습니다.")

        with col_map:
            # 지도의 세로 크기를 650px로 키움
            self.render_kakao_map(df_students, height=650)

        # 학생 클릭 시 나타나는 하단 로그 섹션
        if st.session_state['selected_student_id']:
            st.write("---")
            st.subheader(f"📊 {st.session_state['selected_student_name']} 학생 상세 이동 로그 (10초 단위)")
            
            logs_df = self.fetch_location_logs(st.session_state['selected_student_id'])
            
            if not logs_df.empty:
                st.dataframe(logs_df, use_container_width=True, height=350)
            else:
                st.warning("기록된 이동 로그가 없습니다.")

# 3. 앱 실행
if __name__ == "__main__":
    app = EyeLinkApp()
    app.show_dashboard()