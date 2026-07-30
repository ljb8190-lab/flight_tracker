import os
import re
import requests

# 1. 환경 변수 (GitHub Secrets)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

# 2. 항공권 조회 조건 설정
DEPARTURE_AIRPORT = "ICN"  # 인천
ARRIVAL_AIRPORT = "HKG"    # 홍콩

OUTBOUND_DATE = "2026-11-26"  # 가는 날 (목)
RETURN_DATE = "2026-11-29"    # 오는 날 (일)

# 🕒 시간대 범위 설정 (24시간제 HH:MM)
OUT_DEP_START = "06:00"  # 가는 편 출발 시작
OUT_DEP_END   = "14:00"  # 가는 편 출발 마감

RET_DEP_START = "12:00"  # 오는 편 출발 시작
RET_DEP_END   = "22:00"  # 오는 편 출발 마감

MAX_PRICE = 550000  # 목표 감시 가격 (원)

# 🇰🇷 국내 항공사 정의 목록
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
    """국내 항공사 여부 체크"""
    if not airline_name:
        return False
    return any(kr_name.lower() in str(airline_name).lower() for kr_name in KOREAN_AIRLINES)

def parse_time_to_24h(raw_time_str):
    """
    '2026-11-26 09:30', '9:30 AM', '2:15 PM+1', '14:20' 등
    어떤 형태의 시간 데이터든 'HH:MM' (24시간제) 포맷으로 완벽 정규화
    """
    if not raw_time_str or not isinstance(raw_time_str, str):
        return ""
    
    # 1) 날짜 부분 제거 ('2026-11-26 09:30' -> '09:30')
    time_str = re.sub(r'^\d{4}-\d{2}-\d{2}\s+', '', raw_time_str.strip())
    
    # 2) 익일 표시 제거 ('+1', '+2', '(+1)' 등)
    time_str = re.sub(r'\s*\(\+\d+\)|\+\d+', '', time_str).strip()
    
    # 3) 12시간제 (9:30 AM / 02:15 PM) 정규식 매칭
    match_12 = re.match(r'^(\d{1,2}):(\d{2})\s*(AM|PM)$', time_str, re.IGNORECASE)
    if match_12:
        hh = int(match_12.group(1))
        mm = int(match_12.group(2))
        ampm = match_12.group(3).upper()
        if ampm == "PM" and hh < 12:
            hh += 12
        elif ampm == "AM" and hh == 12:
            hh = 0
        return f"{hh:02d}:{mm:02d}"
        
    # 4) 24시간제 (09:30 / 14:20) 정규식 매칭
    match_24 = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
    if match_24:
        hh = int(match_24.group(1))
        mm = int(match_24.group(2))
        return f"{hh:02d}:{mm:02d}"
        
    return time_str

def get_leg_info(leg):
    """개별 비행 구간(leg)에서 항공사, 편명, 출발/도착 시간을 안전하게 파싱"""
    if not isinstance(leg, dict):
        return "미상", "", "", ""
        
    airline = leg.get("airline", "")
    flight_no = leg.get("flight_number", "")
    
    # SerpApi 실제 키 구조: leg -> departure_airport -> time
    dep_airport = leg.get("departure_airport")
    raw_dep = dep_airport.get("time", "") if isinstance(dep_airport, dict) else leg.get("departure_time", "")
        
    arr_airport = leg.get("arrival_airport")
    raw_arr = arr_airport.get("time", "") if isinstance(arr_airport, dict) else leg.get("arrival_time", "")
        
    return airline, flight_no, parse_time_to_24h(raw_dep), parse_time_to_24h(raw_arr)

def send_telegram_msg(message):
    """텔레그램 메시지 발송 함수"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
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
        print(f"🔍 API 수집 완료 (총 {len(flights_list)}개 항목)")

        matched_deals = []

        for idx, flight in enumerate(flights_list, 1):
            price = flight.get("price", 0)
            legs = flight.get("flights", [])
            
            if not legs:
                print(f"[{idx}] 스킵: 세부 비행 정보(legs) 없음")
                continue

            # 왕편 및 복편 정보 추출
            if len(legs) >= 2:
                out_airline, out_flight_no, out_dep_time, out_arr_time = get_leg_info(legs[0])
                ret_airline, ret_flight_no, ret_dep_time, ret_arr_time = get_leg_info(legs[-1])
            else:
                out_airline, out_flight_no, out_dep_time, out_arr_time = get_leg_info(legs[0])
                ret_airline, ret_flight_no = out_airline, out_flight_no
                ret_dep_time = parse_time_to_24h(flight.get("return_departure_time", out_dep_time))
                ret_arr_time = parse_time_to_24h(flight.get("return_arrival_time", out_arr_time))

            # 최상단 개체 백업 처리
            if not out_airline or out_airline == "미상":
                out_airline = flight.get("airline", "미상")
            if not ret_airline or ret_airline == "미상":
                ret_airline = flight.get("airline", "미상")

            print(f"[{idx}] {out_airline}/{ret_airline} | {price:,}원 | 가는편: {out_dep_time} | 오는편: {ret_dep_time}")

            # 1) 가격 조건 검증
            if price > MAX_PRICE:
                print(f"  └ ❌ 가격 초과 (목표: {MAX_PRICE:,}원 / 현재: {price:,}원)")
                continue

            # 2) 가는 편 시간대 검증
            if not (OUT_DEP_START <= out_dep_time <= OUT_DEP_END):
                print(f"  └ ❌ 가는 편 시간 불일치 ({out_dep_time} / 기준: {OUT_DEP_START}~{OUT_DEP_END})")
                continue

            # 3) 오는 편 시간대 검증
            if not (RET_DEP_START <= ret_dep_time <= RET_DEP_END):
                print(f"  └ ❌ 오는 편 시간 불일치 ({ret_dep_time} / 기준: {RET_DEP_START}~{RET_DEP_END})")
                continue

            print("  └ ✅ 모든 조건 만족! 수집 완료")

            # 🇰🇷 국적기 포함 여부
            has_korean = is_korean_airline(out_airline) or is_korean_airline(ret_airline)

            matched_deals.append({
                "price": price,
                "is_korean": has_korean,
                "out_airline": out_airline,
                "out_flight_no": out_flight_no,
                "out_dep_time": out_dep_time,
                "out_arr_time": out_arr_time,
                "ret_airline": ret_airline,
                "ret_flight_no": ret_flight_no,
                "ret_dep_time": ret_dep_time,
                "ret_arr_time": ret_arr_time,
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
        sorted_deals = sorted(deals, key=lambda x: (not x['is_korean'], x['price']))[:5]
        has_kr_airline = any(deal['is_korean'] for deal in sorted_deals)

        msg = f"✈️ *조건에 맞는 홍콩 항공권 발견!*\n\n"
        msg += f"• *구간:* 인천(ICN) ⇄ 홍콩(HKG)\n"
        msg += f"• *일정:* {OUTBOUND_DATE} ~ {RETURN_DATE}\n"
        msg += f"• *안내:* {'🇰🇷 국내 항공사 우선' if has_kr_airline else '🌐 외항사 검색 결과'}\n"
        msg += f"───────────────\n\n"

        for deal in sorted_deals:
            badge = "🇰🇷 " if deal['is_korean'] else "🌐 "
            msg += f"💰 *왕복 총액:* {deal['price']:,}원\n"
            msg += f"🛫 *가는 편 ({badge}{deal['out_airline']} {deal['out_flight_no']})*\n"
            msg += f"   시간: {deal['out_dep_time']} ➔ {deal['out_arr_time']}\n"
            msg += f"🛬 *오는 편 ({badge}{deal['ret_airline']} {deal['ret_flight_no']})*\n"
            msg += f"   시간: {deal['ret_dep_time']} ➔ {deal['ret_arr_time']}\n\n"

        send_telegram_msg(msg)
    else:
        print("\n결과: 지정한 조건(가격/시간대)을 모두 만족하는 항공권이 없습니다.")

if __name__ == "__main__":
    main()
