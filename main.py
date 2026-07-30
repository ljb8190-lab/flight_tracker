import os
import requests

# 1. 환경 변수 (GitHub Secrets)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

# 2. 항공권 조회 조건 설정
DEPARTURE_AIRPORT = "ICN"  # 인천 (Incheon)
ARRIVAL_AIRPORT = "HKG"    # 홍콩 (Hong Kong)

OUTBOUND_DATE = "2026-11-26"  # 가는 날 (목)
RETURN_DATE = "2026-11-29"    # 오는 날 (일)

# 🕒 시간대 범위 설정 (24시간제 HH:MM)
OUT_DEP_START = "06:00"  # 가는 편 출발 시작 (오전 6시)
OUT_DEP_END   = "14:00"  # 가는 편 출발 마감 (오후 2시)

RET_DEP_START = "12:00"  # 오는 편 출발 시작 (정오 12시)
RET_DEP_END   = "22:00"  # 오는 편 출발 마감 (밤 10시)

MAX_PRICE = 400000  # 목표 감시 가격 (원)

# 🇰🇷 국내 항공사 우선 및 필터 설정
# True : 국내 항공사 결과만 수집 / False : 전체 수집하되 국내 항공사 우선 표시
KOREAN_AIRLINES_ONLY = True  

KOREAN_AIRLINES = [
    "Korean Air", "대한항공", 
    "Asiana Airlines", "아시아나항공", 
    "Jeju Air", "제주항공", 
    "Jin Air", "진에어", 
    "T'way Air", "티웨이항공", 
    "Air Busan", "에어부산", 
    "Air Seoul", "에어서울", 
    "Aero K", "에어로케이"
]

def is_korean_airline(airline_name):
    """항공사 이름이 국내 항공사 목록에 포함되는지 확인"""
    if not airline_name:
        return False
    return any(kr_name.lower() in airline_name.lower() for kr_name in KOREAN_AIRLINES)

def send_telegram_msg(message):
    """텔레그램 메시지 발송 함수"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        print("텔레그램 알림 전송 성공")
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def check_flights():
    """Google Flights API(via SerpApi)를 통한 항공권 조회"""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_flights",
        "departure_id": DEPARTURE_AIRPORT,
        "arrival_id": ARRIVAL_AIRPORT,
        "outbound_date": OUTBOUND_DATE,
        "return_date": RETURN_DATE,
        "currency": "KRW",
        "hl": "ko",
        "api_key": SERPAPI_KEY
    }

    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        flights_list = data.get("best_flights", []) + data.get("other_flights", [])
        matched_deals = []

        for flight in flights_list:
            price = flight.get("price", 0)
            
            if price > MAX_PRICE:
                continue

            legs = flight.get("flights", [])
            if len(legs) < 2:
                continue

            outbound_leg = legs[0]
            return_leg = legs[1]

            out_airline = outbound_leg.get("airline", "항공사 미상")
            ret_airline = return_leg.get("airline", "항공사 미상")

            # 🇰🇷 국내 항공사 여부 확인
            is_out_kr = is_korean_airline(out_airline)
            is_ret_kr = is_korean_airline(ret_airline)
            is_kr_flight = is_out_kr or is_ret_kr  # 왕편 또는 복편 중 국적기 포함 여부

            # 국내 항공사 전용 옵션이 True일 때 외항사만 있는 경우 건너뜀
            if KOREAN_AIRLINES_ONLY and not (is_out_kr and is_ret_kr):
                continue

            # 출발 시간 추출
            out_dep_time = outbound_leg.get("departure_token", {}).get("time", "")
            ret_dep_time = return_leg.get("departure_token", {}).get("time", "")

            # 🕒 시간대 필터링
            if not (OUT_DEP_START <= out_dep_time <= OUT_DEP_END):
                continue
            if not (RET_DEP_START <= ret_dep_time <= RET_DEP_END):
                continue

            matched_deals.append({
                "price": price,
                "is_korean": is_kr_flight,
                "out_airline": out_airline,
                "out_flight_no": outbound_leg.get("flight_number", ""),
                "out_dep_time": out_dep_time,
                "out_arr_time": outbound_leg.get("arrival_token", {}).get("time", ""),
                
                "ret_airline": ret_airline,
                "ret_flight_no": return_leg.get("flight_number", ""),
                "ret_dep_time": ret_dep_time,
                "ret_arr_time": return_leg.get("arrival_token", {}).get("time", ""),
            })

        return matched_deals

    except Exception as e:
        print(f"항공권 조회 중 오류 발생: {e}")
        return []

def main():
    if not all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, SERPAPI_KEY]):
        print("에러: GitHub Secrets 설정이 누락되었습니다.")
        return

    print(f"[{DEPARTURE_AIRPORT} ⇄ {ARRIVAL_AIRPORT} / {OUTBOUND_DATE} ~ {RETURN_DATE}] 항공권 감시 시작...")
    deals = check_flights()

    if deals:
        # 1 순위: 국내 항공사 여부(True가 먼저), 2 순위: 가격(저렴한 순) 정렬
        sorted_deals = sorted(deals, key=lambda x: (not x['is_korean'], x['price']))[:5]

        msg = f"✈️ *조건에 맞는 홍콩 항공권 발견!*\n\n"
        msg += f"• *구간:* 인천(ICN) ⇄ 홍콩(HKG)\n"
        msg += f"• *일정:* {OUTBOUND_DATE} ~ {RETURN_DATE}\n"
        msg += f"• *필터:* {'🇰🇷 국내 항공사 전용' if KOREAN_AIRLINES_ONLY else '국내 항공사 우선'}\n"
        msg += f"───────────────\n\n"

 
