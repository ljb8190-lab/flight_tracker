import os
import re
import requests

# 1. 환경 변수 (GitHub Secrets)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

# 2. 항공권 조회 조건 설정
DEPARTURE_AIRPORT = "ICN"  # 인천
ARRIVAL_AIRPORT = "OKA"    # 오키나와

OUTBOUND_DATE = "2026-11-26"  # 가는 날 (목)
RETURN_DATE = "2026-11-29"    # 오는 날 (일)

# 🕒 시간대 범위 설정 (24시간제 HH:MM)
OUT_DEP_START = "06:00"  # 가는 편 출발 시작
OUT_DEP_END   = "12:00"  # 가는 편 출발 마감

RET_DEP_START = "10:00"  # 오는 편 출발 시작
RET_DEP_END   = "18:00"  # 오는 편 출발 마감

MAX_PRICE = 400000  # 목표 감시 가격 (원)

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
    """'2026-11-26 09:30', '9:30 AM', '2:15 PM+1' 등을 'HH:MM' (24시간제) 포맷으로 완벽 변환"""
    if not raw_time_str or not isinstance(raw_time_str, str):
        return ""
    
    # 날짜 및 익일(+1) 표시 제거
    time_str = re.sub(r'^\d{4}-\d{2}-\d{2}\s+', '', raw_time_str.strip())
    time_str = re.sub(r'\s*\(\+\d+\)|\+\d+', '', time_str).strip()
    
    # 12시간제 (9:30 AM / 02:15 PM) 매칭
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
        
    # 24시간제 (09:30 / 14:20) 매칭
    match_24 = re.match(r'^(\d{1,2}):(\d{2})$', time_str)
    if match_24:
        hh = int(match_24.group(1))
        mm = int(match_24.group(2))
        return f"{hh:02d}:{mm:02d}"
        
    return time_str

def get_leg_info(leg):
    """개별 비행 구간(leg) 정보 파싱"""
    if not isinstance(leg, dict):
        return "미상", "", "", ""
        
    airline = leg.get("airline", "")
    flight_no = leg.get("flight_number", "")
    
    dep_airport = leg.get("departure_airport")
    raw_dep = dep_airport.get("time", "") if isinstance(dep_airport, dict) else leg.get("departure_time", "")
        
    arr_airport = leg.get("arrival_airport")
    raw_arr = arr_airport.get("time", "") if isinstance(arr_airport, dict) else leg.get("arrival_time", "")
        
    return airline, flight_no, parse_time_to_24h(raw_dep), parse_time_to_24h(raw_arr)

def fetch_return_flights(departure_token):
    """선택한 가는 편 토큰(departure_token)을 이용해 실제 오는 편(복편) 목록 조회"""
    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_flights",
        "departure_id": DEPARTURE_AIRPORT,
        "arrival_id": ARRIVAL_AIRPORT,
        "outbound_date": OUTBOUND_DATE,
        "return_date": RETURN_DATE,
        "departure_token": departure_token,
        "currency": "KRW",
        "hl": "ko",
        "api_key": SERPAPI_KEY
    }
    try:
        res = requests.get(url, params=params)
        data = res.json()
        return data.get("best_flights", []) + data.get("other_flights", [])
    except Exception as e:
        print(f"복편 상세 조회 실패: {e}")
        return []

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
    """Google Flights API를 통한 2단계 왕복 항공권 검증 및 수집"""
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
        outbound_list = data.get("best_flights", []) + data.get("other_flights", [])
        print(f"🔍 1차 가는 편 검색 완료 (총 {len(outbound_list)}개 후보 수집)")

        matched_deals = []

        for idx, flight in enumerate(outbound_list, 1):
            price = flight.get("price", 0)
            legs = flight.get("flights", [])
            departure_token = flight.get("departure_token")

            if not legs:
                continue

            out_airline, out_flight_no, out_dep_time, out_arr_time = get_leg_info(legs[0])
            if not out_airline or out_airline == "미상":
                out_airline = flight.get("airline", "미상")

            # 1) 가격 검증
            if price > MAX_PRICE:
                print(f"[{idx}] {out_airline} | ❌ 가격 초과 ({price:,}원 / 목표 {MAX_PRICE:,}원)")
                continue

            # 2) 가는 편 시간대 검증
            if not (OUT_DEP_START <= out_dep_time <= OUT_DEP_END):
                print(f"[{idx}] {out_airline} | ❌ 가는 편 시간 불일치 ({out_dep_time})")
                continue

            print(f"[{idx}] {out_airline} | ✅ 가는 편 조건 만족 ({out_dep_time}, {price:,}원) ➔ 복편 2차 조회 진행...")

            # 3) departure_token으로 2차 복편(오는 편) 조회
            if not departure_token:
                print("  └ ❌ departure_token이 없어 복편 스케줄을 조회할 수 없음")
                continue

            return_flights = fetch_return_flights(departure_token)
            
            for ret_flight in return_flights:
                ret_legs = ret_flight.get("flights", [])
                if not ret_legs:
                    continue
                
                ret_airline, ret_flight_no, ret_dep_time, ret_arr_time = get_leg_info(ret_legs[0])
                if not ret_airline or ret_airline == "미상":
                    ret_airline = ret_flight.get("airline", "미상")

                # 4) 오는 편 시간대 검증 (12:00 ~ 22:00)
                if RET_DEP_START <= ret_dep_time <= RET_DEP_END:
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
                    print(f"  └ 🎉 복편 스케줄 확인 완료! ({ret_airline} {ret_flight_no} | 출발: {ret_dep_time})")

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
        # 중복 조합 제거 (동일 편명 및 시간 중복 방지)
        unique_deals = []
        seen = set()
        for d in deals:
            identifier = (d['out_flight_no'], d['ret_flight_no'], d['price'])
            if identifier not in seen:
                seen.add(identifier)
                unique_deals.append(d)

        sorted_deals = sorted(unique_deals, key=lambda x: (not x['is_korean'], x['price']))[:5]
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
        print("\n결과: 지정한 조건(가격/시간대)을 만족하는 완벽한 왕복 항공권이 없습니다.")

if __name__ == "__main__":
    main()
