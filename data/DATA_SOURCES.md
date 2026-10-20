# Data sources (Kyoto)

All 25 places in `places.json` are real places in Kyoto, Japan. Each `source` is the official page that was opened to confirm both the hours and the price, so every row has `verified: true`. Hours are the October 2026 (autumn) hours. Visit durations are estimates, except Gion Corner (50 min) and the Hozugawa boat (120 min), which are stated by the source.

## Currency

Costs are whole SGD per person. Yen prices were converted at 123.53 JPY per SGD, from the ECB reference rates of 16 Oct 2026 (177.82 JPY and 1.4395 SGD per EUR), then rounded. Scenario budgets in `scripts/generate_scenarios.py` use the same SGD units: tight 30 to 50, loose 120 to 180 for a two-day trip.

## Areas

| Area | Kyoto districts |
| --- | --- |
| centre | Kawaramachi, Shijo, Nijo |
| east | Higashiyama, Gion, Okazaki, Nanzen-ji, Ginkaku-ji |
| north | Kinkaku-ji, Kitano, Botanical Gardens, Kurama |
| south | Kyoto Station, Fushimi Inari, To-ji |
| west | Arashiyama, Sagano |

`travel_times.json` holds typical door-to-door minutes by public transport between district centres. They are estimates anchored on the official Kyoto City tourism access pages, for example Kyoto Station to Shijo 4 min by subway, to Saga-Arashiyama 11 min by JR, to Ginkaku-ji about 43 min and to JR Inari 9 min ([kyoto.travel getting around](https://kyoto.travel/en/getting-around/)). The east-north, east-west, north-west, north-south and centre-west pairs have no direct source and are rough estimates.

## Places

| id | Place | Area | Yen | SGD | Hours used | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| p01 | [Ippodo Tea Kyoto Main Store](https://global.ippodo-tea.co.jp/pages/store-kyoto) | centre | 972 | 8 | 10:00-17:00 | 972 yen is the take-out matcha price listed on the page; other take-out drinks are 756-972 yen. Tearoom menu prices are in a PDF not checked. |
| p02 | [Kyoto International Manga Museum](https://kyotomm.jp/en/guide-inuse/) | centre | 1200 | 10 | 10:00-17:00 | 1,200 yen is the individual fee for ages 19 and up. Hours 10:00-17:00 (last admission 16:30). |
| p03 | [Nijo Castle](https://nijo-jocastle.city.kyoto.lg.jp/visit/fee/?lang=en) | centre | 1300 | 11 | 08:45-17:00 | 1,300 yen covers castle admission plus the Ninomaru-goten Palace. Hours from the top page (https://nijo-jocastle.city.kyoto.lg.jp/?lang=en): entry 08:45-16:00, site closes 17:00. |
| p04 | [Ginkaku-ji (Silver Pavilion)](https://www.shokoku-ji.jp/en/ginkakuji/access/) | east | 1000 | 8 | 08:30-17:00 | Hours are 08:30-17:00 Mar 1-Nov 30 and 09:00-16:30 Dec 1-Feb 28. The page shows 'General' admission as 1,000 yen and says fees may change during special exhibitions. |
| p05 | [Gion Corner](https://www.kyoto-gioncorner.com/global/en.html) | east | 5500 | 45 | 18:00-19:50 | Adult ticket 5,500 yen. Shows start daily at 18:00 and 19:00 and last about 50 minutes; 19:50 is the end of the last show. |
| p06 | [Heian Jingu Shrine Shin-en Garden](https://www.heianjingu.or.jp/map/garden/) | east | 600 | 5 | 08:30-17:30 | The cost, open and close values are for the Shin-en garden: adults 600 yen; open 08:30-18:00 Mar 1-Sep 30 (entry until 17:30), to 17:30 in October, to 17:00 Nov-Feb. On Oct 22 (Jidai Matsuri). |
| p07 | [Kyoto National Museum](https://www.kyohaku.go.jp/eng/visit/info/) | east | 700 | 6 | 09:30-17:00 | 700 yen is the Collection Galleries fee for adults. Fridays open until 20:00 (last entry 19:30). |
| p08 | [Nanzen-ji](https://nanzenji.or.jp/about_rinzaishu/visit) | east | 600 | 5 | 08:40-17:00 | Hojo garden is 600 yen, Sanmon gate 600 yen, Nanzen-in 500 yen. The page does not say whether the grounds are free. |
| p09 | [Nanzenji Junsei](https://to-fu.co.jp/menu/) | east | 3850 | 31 | 11:00-21:30 | 3,850 yen (tax included) is the cheapest yudofu course ('花コース'); others are 4,950, 5,830, 7,700-9,350, and 11,000-16,500 yen. |
| p10 | [National Museum of Modern Art, Kyoto (MOMAK)](https://www.momak.go.jp/English/guide/) | east | 1000 | 8 | 10:00-18:00 | 1,000 yen is the Collection Gallery fee for adults. Fridays open until 20:00, with an 800 yen night fee from 18:00. |
| p11 | [Kinkaku-ji (Golden Pavilion)](https://www.shokoku-ji.jp/en/kinkakuji/access/) | north | 500 | 4 | 09:00-17:00 | 'General' admission 500 yen. Hours may change for special exhibitions. |
| p12 | [Kitano Tenmangu Shrine](https://kitanotenmangu.or.jp/access/) | north | 0 | 0 | 07:00-17:00 | The page states the grounds are free ('境内の拝観は自由です') and open 07:00-17:00. |
| p13 | [Kurama-dera](https://prev.kyoto.travel/ms/shrine_temple/143) | north | 200 | 2 | 09:00-16:00 | This is an older (prev.) version of the official tourism site and may be out of date: it lists '9:00-16:00' and 'Higher than high school student 200 yen'. |
| p14 | [Kyoto Botanical Gardens](https://www.kyotobotanicalgardens.jp/english) | north | 500 | 4 | 09:00-17:00 | 500 yen is the adult fee. Last admission 16:00. |
| p15 | [Fushimi Inari Taisha](https://prev.kyoto.travel/ms/shrine_temple/180) | south | 0 | 0 | 07:00-18:30 | Page (older 'prev.' version of the official Kyoto City tourism site) lists 'Hours: 7:00-18:30 / 8:30-16:30 (Prayer)' and 'Entrance fee: Free'. |
| p16 | [Gekkeikan Okura Sake Museum](http://www.gekkeikan.com/museum/) | south | 600 | 5 | 09:30-16:30 | 600 yen is the adult fee (ages 20 and up). Last admission 16:00. |
| p17 | [Kyoto Aquarium](https://en.kyoto-aquarium.com/about/price/) | south | 2600 | 21 | 10:00-18:30 | 2,600 yen is adult general admission. Hours vary by date: https://en.kyoto-aquarium.com/about/access/ shows only Oct 3 2026 (10:00-18:30, last entry 17:30), and other dates are on the site calendar. |
| p18 | [Kyoto Railway Museum](https://www.kyotorailwaymuseum.jp/en/) | south | 1500 | 12 | 10:00-17:00 | 1,500 yen is general admission for ages 18 and up. Last admission 16:30. |
| p19 | [Kyoto Ramen Koji](https://www.kyoto-station-building.co.jp/ramen_koji/) | south | 1100 | 9 | 11:00-22:00 | 1,100 yen is an approximate meal cost per person: the page lists 10 ramen shops with main bowls from 880 to 2,400 yen, most between 930 and 1,280 yen. Last order 21:30. |
| p20 | [Kyoto Tower Sando](https://kyoto-tower-sando.jp/) | south | 1000 | 8 | 11:00-23:00 | Hours by floor: B1F 11:00-23:00, 1F 10:00-21:00, 2F 10:00-19:00; some shops differ. The 1,000 yen cost is approximate, based on a '1,000円ランチ' banner (another item mentions an 890 yen meal). |
| p21 | [Kyoto Tower Observation Deck](https://www.kyoto-tower.jp/fee/) | south | 1000 | 8 | 10:00-21:00 | 1,000 yen is the adult same-day ticket (tax included). Last entry 20:30. |
| p22 | [To-ji](https://toji.or.jp/en/location/index.html) | south | 800 | 6 | 08:00-17:00 | The temple gate is open 05:00-17:00. Kondo and Kodo halls are open 08:00-17:00 (last admission 16:30). |
| p23 | [Hozugawa River Boat Ride](https://ja.kyoto.travel/event/single.php?event_id=4450) | west | 6000 | 49 | 09:00-15:00 | Source is the Kyoto City official tourism site (京都観光Navi). Adult 6,000 yen, child 4,500 yen. |
| p24 | [Jojakko-ji Temple](https://www.jojakko-ji.or.jp/) | west | 600 | 5 | 09:00-17:00 | Official page: 9:00-17:00, last entry 16:30, fee 600 yen. |
| p25 | [Tenryu-ji](https://www.tenryuji.com/en/visit/) | west | 500 | 4 | 08:30-17:00 | 500 yen is the garden fee for high-school age and up. Garden plus buildings is 800 yen (garden fee + 300). |

## Known limits

- Kurama-dera is filed under north, but it is about an hour from central Kyoto, so its real travel time is longer than the north row says.
- Fushimi Inari and Kurama-dera hours come from the archived version of the official Kyoto tourism site. Kurama-dera's 200 yen fee may be out of date.
- To-ji uses its hall hours (08:00-17:00) and the 800 yen hall fee. The grounds open at 05:00 and are free.
- Restaurant and food-hall costs (Ramen Koji, Kyoto Tower Sando, Ippodo, Junsei) are typical per-person spends taken from menu prices on the source page.
- No verified place has the `markets` tag. Nishiki Market publishes no official hours, so it was left out, and the generator no longer gives friends a `markets` like.
- Prices and hours change. Re-check the sources before relying on them for a real trip.
