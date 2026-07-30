import os
import requests

# 1. 환경 변수
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

# 2. 조회 조건
DEPARTURE_AIRPORT = "ICN"
ARRIVAL_AIRPORT = "HKG"

OUTBOUND_DATE = "2026-11-26"
RETURN_DATE = "2026-11-29"

# 시간대 조건
OUT_DEP_START = "06:00"
OUT_DEP_END   = "14:00"

RET_DEP_START = "12:00"
RET_DEP_END   = "22:00"

# 테스트를 위해 목표 가격을 살짝 여유 있게 잡거나(예: 60만원) 상향 테스트 추천
MAX_PRICE = 500000  

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
    if not airline_name:
        return False
    return any(kr_name.lower() in str(airline_name).lower() for kr_name in KOREAN_AIRLINES)

def parse_time_to_24h(time_str):
    """'9:30 AM' 또는 '09:30' 형태의 시간을 '09:30' (24시간) 포맷으로 통일"""
    if not time_str:
        return ""
    time_str = time_str.strip()
    # 이미 24시간 포맷("09:30")인 경우
    if "AM" not in time_str and "PM" not in time_str:
        parts = time_str.split(":")
        if len(parts) == 2:
            return f"{int(parts[0]):02d}:{parts[1]}"
        return time_str
    
    # AM/PM 포함된 경우 ("09:30 AM")
    try:
        from datetime import datetime
        dt = datetime.strptime(time_str, "%I:%M %p")
        return dt.strftime("%H:%M")
    except:
        return time_str

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload)
        res.raise_for_status()
        print("텔레그램 알림 전송 성공")
    except Exception as e:
        print(f"텔레그램 전송 실패: {e}")

def check_flights():
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
        print(f"🔍 API에서 수집된 전체 항공편 개수: {len(flights_list)}개")

        matched_deals = []

        for idx, flight in enumerate(flights_list, 1):
            price = flight.get("price", 0)
            legs = flight.get("flights", [])
            
            if len(legs) < 2:
                print(f"[{idx}] 스킵: 왕복 편수 부족")
                continue

            outbound_leg = legs[0]
            return_leg = legs[1]

            out_airline = outbound_leg.get("airline", "미상")
            ret_airline = return_leg.get("airline", "미상")

            # 시간 추출 및 24시간제 정규화
            raw_out_time = outbound_leg.get("departure_token", {}).get("time") or outbound_leg.get("departure_time", "")
            raw_ret_time = return_leg.get("departure_token", {}).get("time") or return_leg.get("departure_time", "")
            
            out_dep_time = parse_time_to_24h(raw_out_time)
            ret_dep_time = parse_time_to_24h(raw_ret_time)

            # 디버깅 로그 출력
            print(f"[{idx}] {out_airline}/{ret_airline} | 가격: {price:,}원 | 가는편: {out_dep_time} | 오는편: {ret_dep_time}")

            # 1) 가격 검증
            if price > MAX_PRICE:
                print(f"  └ ❌ 가격 초과 (목표가 {MAX_PRICE:,}원 / 현재가 {price:,}원)")
                continue

            # 2) 시간 검증
            if not (OUT_DEP_START <= out_dep_time <= OUT_DEP_END):
                print(f"  └ ❌ 가는 편 시간 불일치 ({out_dep_time} != {OUT_DEP_START}~{OUT_DEP_END})")
                continue

            if not (RET_DEP_START <= ret_dep_time <= RET_DEP_END):
                print(f"  └ ❌ 오는 편 시간 불일치 ({ret_dep_time} != {RET_DEP_START}~{RET_DEP_END})")
                continue

            print("  └ ✅ 모든 조건 만족!")

            is_out_kr = is_korean_airline(out_airline)
            is_ret_kr = is_korean_airline(ret_airline)

            matched_deals.append({
                "price": price,
                "is_korean": is_out_kr and is_ret_kr,
                "out_airline": out_airline,
                "out_flight_no": outbound_leg.get("flight_number", ""),
                "out_dep_time": out_dep_time,
                "out_arr_time": parse_time_to_24h(outbound_leg.get("arrival_token", {}).get("time") or outbound_leg.get("arrival_time", "")),
                "ret_airline": ret_airline,
                "ret_flight_no": return_leg.get("flight_number", ""),
                "ret_dep_time": ret_dep_time,
                "ret_arr_time": parse_time_to_24h(return_leg.get("arrival_token", {}).get("time") or return_leg.get("arrival_time", "")),
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
        print(f"\n결과: 조건을 만족하는 항공권이 없습니다.")

if __name__ == "__main__":
    main()
