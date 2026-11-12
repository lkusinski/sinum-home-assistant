# Most Home Assistant / Zigbee2MQTT ↔ Sinum (SinumBridge)

Celem mostu jest udostępnienie wybranych urządzeń z Home Assistant (np. Zigbee2MQTT, ESPHome, Z-Wave, Shelly) w ekosystemie Sinum w sposób dwukierunkowy i w czasie rzeczywistym, bez tworzenia pętli sprzężenia zwrotnego i bez modyfikowania konfiguracji źródłowej.

Most jest **wbudowanym, asynchronicznym komponentem integracji** (`custom_components/sinum_home_assistant/bridge.py`), działającym w cyklu życia Home Assistant (bez konieczności uruchamiania zewnętrznych skryptów czy usług systemd).

---

## Zasady działania i bezpieczeństwo

1. **Źródło odczytu**: Most subskrybuje wewnętrzną magistralę zdarzeń Home Assistant (`state_changed`). Nie ingeruje w konfigurację urządzeń Zigbee ani brokera MQTT.
2. **Kierunek dwukierunkowy w czasie rzeczywistym**:
   - **HA → Sinum**: Zmiana stanu encji w Home Assistant natychmiast wysyła polecenie REST/PATCH do wirtualnego urządzenia w chmurze Sinum.
   - **Sinum → HA**: Asynchroniczny klient WebSocket STOMP/SockJS subskrybuje kanał `/topic/<deviceId>`. Akcja użytkownika w aplikacji Sinum (suwak jasności, zmiana barwy, przełącznik) natychmiast wywołuje odpowiednią usługę w Home Assistant (`light.turn_on`, `switch.turn_on` itp.).
3. **Eliminacja pętli (Echo Suppression)**: Mechanizm tłumienia echa sprawdza ostatnio wysłane stany (`_ha_last`, `_recent`) i ignoruje zdarzenia zwrotne wynikające z własnych poleceń.
4. **Izolacja encji w HA**: Wirtualne urządzenia tworzone w chmurze Sinum są oznaczane unikalnym znacznikiem `integration_uid: z2m-bridge`. Główny koordynator integracji odfiltrowuje je, dzięki czemu nie są one ponownie importowane do Home Assistant jako zdublowane encje.

---

## Wybór urządzeń za pomocą etykiet

Wybór urządzeń i encji do mostu odbywa się deklaratywnie w Home Assistant:

1. Oznacz wybrane urządzenie lub encję etykietą **`sinumbridge`** (domyślna etykieta, z możliwością zmiany w opcjach integracji; etykieta legacy `sinum` jest również akceptowana).
2. Mapper odczytuje rejestr urządzeń i encji HA, filtruje encje wyłączone lub ukryte, a następnie automatycznie tworzy lub aktualizuje wirtualne urządzenia w chmurze Sinum.
3. Mapowanie jest utrwalane w magazynie Home Assistant (`.storage/sinum_home_assistant.bridge`), z możliwością jednorazowego importu z pliku `mapping.json`.

---

## Obsługiwane klasy urządzeń i warianty Sinum

| Klasa urządzenia w HA | Wariant wirtualny Sinum | Kontrolki i elementy UI Sinum | Obsługiwane funkcje i normalizacja |
|---|---|---|---|
| **Oświetlenie (`light`)** | `generic` | `color_picker` | Włącz/Wyłącz, jasność (0–100%), kolor RGB (HEX), temperatura barwowa (Kelvin). Sinum używa trybu `temperature`, a HA `color_temp`; most dokonuje automatycznej normalizacji. |
| **Kontaktrony / czujniki otwarcia** | `two_state_input_sensor` | `text` | Wyświetla `Otwarte` lub `Zamknięte`. Obsługuje odwrócenie logiki (`invert: true`). |
| **Bramy wjazdowe i garażowe** | `gate` (wirtualna) / `relay` | `switcher` / status | Impuls sterujący `turn_on` / zwalnianie przekaźnika. Czujnik zamknięcia bramy w Sinum (`close_status_sensor`) wymaga logiki odwróconej (`true` = zamknięta). |
| **Temperatura** | `temperature_sensor` | `text` (tekst-default) | Wartość rejestrowana w formacie Sinum (×10) oraz formatowany ciąg tekstowy (np. `21.4 °C`). |
| **Wilgotność** | `humidity_sensor` | `text` (tekst-default) | Wartość w formacie Sinum (×10) oraz ciąg tekstowy (np. `52.0 %`). |
| **Wielkości analogowe (ciśnienie, napięcie itp.)** | `analog_input` | Wartość wariantu | Dowolna wartość numeryczna z przypisaną jednostką (`unit`). |
| **Pomiary energii i mocy** | `energy_meter` | Wartość wariantu | Pobór mocy (W) oraz zużycie energii (kWh). |
| **Poziom baterii** | `battery` | Wartość wariantu | Stan naładowania (0–100%). |
| **Klimatyzator (`climate`)** | `custom_device_module` | `variant: ac_module` | Tryby pracy (auto, chłodzenie, ogrzewanie, wentylacja, osuszanie), nastawa temperatury zadanej i odczyt temperatury pomieszczenia. |

---

## Statystyki i wykresy InfluxDB w Sinum

Domyślnie chmura Sinum nie rejestruje punktów statystycznych dla wirtualnych urządzeń niestandardowych. Aby wartości z mostu były widoczne na wykresach historycznych w aplikacji Sinum, most wstrzykuje odpowiedni blok skryptu Lua:

```lua
function CustomDevice:onEvent(event)
  self:setValue("status", "online")
  if self:changedVariantDeviceValue("temperature") then
    statistics:addPoint("temperature", self:getVariantDeviceValue("temperature"), unit.celsius_x10)
  end
end
```

Dzięki temu punkty pomiarowe trafiają do bazy InfluxDB w chmurze Sinum i mogą być prezentowane na wykresach po skonfigurowaniu zapytania statystycznego w aplikacji.

---

## Pomiary wydajności i czasy reakcji (Push vs Polling)

Dzięki zastosowaniu protokołu WebSocket STOMP/SockJS opóźnienia w komunikacji dwukierunkowej zostały zredukowane do ułamków sekundy:

- **Brama / impuls**: ~0.45 s
- **Zmiana stanu i jasności światła**: ~0.60–0.90 s
- **Czujnik temperatury i wilgotności**: ~0.45–0.65 s
- **Aktualizacja stanu kontaktronu**: ~1.50–1.80 s

Tradycyjne odpytywanie chmury (polling) zostało zachowane wyłącznie jako proces rekoncyliacji (co 60 s), zapewniający spójność stanów po ewentualnym zerwaniu połączenia internetowego.

---

## Znane ograniczenia techniczne

- **Brak wirtualnego wariantu dla rolet**: Chmurowe API Sinum nie udostępnia typu `cover` dla urządzeń wirtualnych.
- **Kamery RTSP / NVR**: Chmura Sinum odrzuca rejestrację strumieni kamer bez fizycznego rejestratora sprzętowego TECH (`422 NvrDeviceNotFound`).
- **Status custom sensorów**: Wirtualne czujniki w interfejsie Sinum raportują status `unknown`, pomimo że przekazywane wartości i elementy UI działają poprawnie.
- **Relay zarządzany przez termostat**: Przekaźnik przypisany do termostatu wirtualnego nie generuje własnych punktów statystycznych relay w chmurze.
