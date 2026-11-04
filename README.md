# Historia Pojazdu dla Home Assistant

![Logo Historia Pojazdu](https://raw.githubusercontent.com/xmemphis-xyz/ha-historia-pojazdu/main/custom_components/historia_pojazdu/brand/icon.png)

Nieoficjalna integracja, która odczytuje z serwisu [Historia Pojazdu](https://historiapojazdu.gov.pl/) datę ważności OC, termin następnego badania technicznego i stan licznika z ostatniego badania. Nie wymaga MQTT, dodatku ani sterowania przeglądarką.

To rozwinięta wersja [jarekgrzabel/ha-historia-pojazdu](https://github.com/jarekgrzabel/ha-historia-pojazdu). Kod protokołu i parser powstały na podstawie [historia-pojazdu-sdk](https://github.com/Korea77/historia-pojazdu-sdk) (commit `1f4c496ef728011903b308dfa90d74409da05740`). Całość jest udostępniona na licencji GPL-3.0 (plik LICENSE).

## Instalacja

1. Zrób kopię zapasową Home Assistant.
2. W HACS → menu ⋮ → **Niestandardowe repozytoria** dodaj `https://github.com/xmemphis-xyz/ha-historia-pojazdu` jako typ **Integracja**, zainstaluj ją i uruchom HA ponownie. Możesz też ręcznie skopiować katalog `custom_components/historia_pojazdu`.
3. W **Ustawieniach → Urządzenia i usługi → Dodaj integrację** wybierz **Historia Pojazdu** i podaj dane z dowodu rejestracyjnego:
   - nazwę (dowolną, np. „Volvo”),
   - numer rejestracyjny (spacje są usuwane automatycznie),
   - VIN (pole E),
   - datę pierwszej rejestracji (pole B): wybierz ją w kalendarzu albo wpisz jako `RRRR-MM-DD` lub `DD.MM.RRRR`.

   Dane są od razu sprawdzane w usłudze, więc literówka pojawi się jako błąd w formularzu, a nie jako pusty sensor. Każdy samochód to osobny wpis.

Po zmianie tablic rejestracyjnych użyj opcji **Zmień konfigurację** przy wpisie integracji. VIN identyfikuje pojazd i nie podlega zmianie.

## Encje

| Encja | Opis |
|---|---|
| Ważność OC | data, atrybut `aktualnosc` |
| Następne badanie techniczne | data, atrybut `aktualnosc` |
| Ostatni stan licznika z badania | km lub mi, atrybuty `data_odczytu` i `aktualnosc`; ma `state_class`, więc działa w statystykach |
| Ostatnia udana aktualizacja | diagnostyczna; moment pobrania obu dat |
| Stan pobierania | diagnostyczna; `Aktualne` albo opis problemu |
| Odśwież dane | przycisk |

Dane są pobierane w tle po starcie, co 24 godziny i po naciśnięciu przycisku.

Atrybut `aktualnosc` ma wartość `aktualne` po udanym pobraniu albo `zapisane lub nieaktualne`, gdy wartość przywrócono z zapisu lub ostatnie pobranie się nie powiodło. Zapisane wartości przetrwają restart i nie są kasowane po błędzie. Nieznana data OC nie oznacza braku polisy. Jeśli najnowsze badanie nie ma jednoznacznego terminu, poprzedni termin nie jest uznawany za aktualny.

Stan licznika pochodzi wyłącznie z badań technicznych, nie z kontroli drogowych, więc nie jest to bieżący przebieg.

## Przykład: przypomnienie o OC i przeglądzie

Zmień `sensor.*` na swoje encje i `notify.mobile_app_telefon` na swoją akcję powiadomień.

```yaml
alias: Przypomnienie OC i przegląd
triggers:
  - trigger: time
    at: "09:00:00"
conditions: []
actions:
  - repeat:
      for_each:
        - sensor.volvo_waznosc_oc
        - sensor.volvo_nastepne_badanie_techniczne
      sequence:
        - variables:
            dni: >
              {{ ((states(repeat.item) | as_datetime).date() - now().date()).days
                 if states(repeat.item) not in ['unknown', 'unavailable'] else none }}
        - if:
            - condition: template
              value_template: "{{ dni in [30, 14, 7, 1, 0] }}"
          then:
            - action: notify.mobile_app_telefon
              data:
                title: "{{ state_attr(repeat.item, 'friendly_name') }}"
                message: "Termin: {{ states(repeat.item) }} (za {{ dni }} dni)"
mode: single
```

## Bezpieczeństwo i ograniczenia

- Połączenia HTTPS weryfikują certyfikat. Każda próba ma ograniczony czas. Błędy sieci i serwera (5xx, 429) są ponawiane z przerwami. Odrzucenie danych pojazdu (4xx) nie jest ponawiane.
- Wpis integracji zawiera dane pojazdu, więc chroń dostęp do konfiguracji i kopii zapasowych HA. Do pamięci trwałej trafiają tylko daty, czas aktualizacji i odczyt licznika. Logi (także na poziomie `debug`) zawierają jedynie typ błędu i kod HTTP, bez VIN i bez treści odpowiedzi.
- Interfejs serwisu jest nieoficjalny i może się zmienić. Nie traktuj integracji jako jedynego potwierdzenia ważności dokumentów.

Diagnostykę włączysz w `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.historia_pojazdu: debug
```

## Wycofanie

Usuń automatyzacje korzystające z integracji, usuń wpisy Historia Pojazdu w ustawieniach HA, a potem odinstaluj integrację w HACS lub usuń jej katalog. Usunięcie wpisu kasuje też jego zapisane daty.

## Testy

```
python -m unittest discover -s tests
```

Testy wymagają pakietu `aiohttp`. Home Assistant jest w nich zastąpiony atrapami (`tests/_stubs.py`), więc zachowanie w działającym HA trzeba sprawdzić osobno.

## Zmiany i wydania

Historia zmian jest w [CHANGELOG.md](CHANGELOG.md). Nowe wydanie tworzy się samo po zmianie `version` w `manifest.json` na gałęzi `main`, o ile w CHANGELOG jest sekcja `## <wersja>`.
