# Tone Spectrum Analyzer

Ett lokalt skrivbordsprogram i Python för att analysera och jämföra klangspektra från inspelade toner. Projektet är en del av ett gymnasiearbete inom ljudanalys.

Programmet är tänkt att användas för att jämföra exempelvis samma ton spelad på olika gitarrer eller pianon. Målet är att kunna se grundtoner, övertoner och undertoner i frekvensdomänen utan att förlora den harmoniska strukturen vid brusreducering.

## Projektstatus

Projektet byggs stegvis. Följande delar är klara just nu:

- [x] Körbart lokalt PySide6-program
- [x] Huvudfönster med fyra separata flikar
- [x] Guidad inspelning av enskilda toner som FLAC (piano, gitarr, eget instrument)
- [x] Automatisk skapning av programmets datamappar
- [x] Ljudinläsning för WAV, MP3 och FLAC
- [x] Spektral brusreducering med STFT
- [x] Före- och eftervisning av spektrum i brusreduceringsfliken
- [x] Sparande av brusreducerad ljudfil som WAV
- [x] Grundläggande kontrolltest av harmonisk bevaring
- [x] Fullständig FFT-analysflik
- [x] Sparande av FFT-grafer och rådata
- [x] Lagerjämförelse av flera FFT-resultat
- [x] Av/på-kontroller för enskilda lager
- [x] Export av sammanslagna lagergrafer
- [ ] Mer omfattande tester med riktiga inspelningar

## Funktioner

### 1. Toninspelning

Fliken `Note recorder` gör det snabbt att spela in många enskilda toner, till exempel alla tangenter på ett piano eller band 0-12 på alla strängar på en gitarr. Användaren kan:

- Välja instrument: piano med valbart omfång (A0-C8 som standard), gitarr i standardstämning (band 0-12, sträng för sträng från låga E, 78 toner) eller ett eget instrument med namn och tonomfång.
- Välja mikrofon och ett eget mappnamn, exempelvis `Eriks gitarr`.
- Mäta rummets brusnivå så att tröskeln för anslag ställs in automatiskt.
- Se vilken ton som ska spelas härnäst. Inspelningen startar automatiskt vid anslaget och stoppar när tonen har klingat ut.
- Lyssna på tagningen (`L`), ta om den (`R`) och gå vidare till nästa ton (mellanslag).

Varje ton sparas som en FLAC-fil (48 kHz, 24 bit, mono) i `data/raw_audio/<mappnamn>/`, så att filerna direkt kan öppnas i brusreduceringen och FFT-analysen. Filnamnen innehåller instrument, ton och MIDI-nummer, till exempel `piano_C4_060.flac` och `guitar_string6_fret03_G2_043.flac`.

Efterbearbetningen är försiktig så att den inte påverkar klangen:

- Tystnaden före anslaget klipps bort, med 5 ms marginal.
- Tystnaden efter utklingningen klipps bort. 0,3 s svans behålls och avslutas med en mjuk fade-out på 50 ms.
- Ingen normalisering görs, så den naturliga dynamiken mellan tonerna bevaras.

Om signalen klipper, eller om maxlängden nås innan tonen klingat ut, visas en varning.

### 2. Brusreducering

Brusreduceringen är den första färdigbyggda funktionen. Användaren kan:

1. Välja en eller flera ljudfiler (Ctrl/Shift-klick i filväljaren) eller en hel mapp med **Select folder…**. Filerna visas i en lista sorterad efter namn.
2. Klicka på en fil i listan för att läsa in den som en monosignal utan att ändra samplingsfrekvensen.
3. Visa ett spektrum före och efter brusreduceringen.
4. Spara den behandlade signalen som en ny WAV-fil, eller brusreducera och spara alla filer i listan på en gång med **Reduce noise and save all**.

Filer från `data/raw_audio/<mappnamn>/` sparas i `data/cleaned_audio/<mappnamn>/`, så att en inspelningsomgång hålls samlad.

Brusreduceringen använder inte ett enkelt lågpassfilter. Ett lågpassfilter skulle kunna ta bort höga övertoner även om de tillhör själva tonen. I stället används en försiktig spektral gate:

- Signalen delas upp i tids- och frekvensfönster med STFT.
- De tystaste 20 procenten av fönstren används för att uppskatta brusgolvet.
- Frekvenskomponenter nära brusgolvet dämpas med en mjuk mask.
- En maskgolvnivå på 20 procent förhindrar hård bortklippning.
- Lokalt tydliga spektrala toppar skyddas för att bevara grundtoner och övertoner.
- Masken jämnas försiktigt ut för att minska risken för så kallat musikaliskt brus.

Algoritmen kan fortfarande behöva finjusteras för olika typer av inspelningar. Särskilt varierande eller icke-stationärt brus bör testas med riktiga ljudfiler innan slutliga slutsatser dras i rapporten.

### 3. FFT-analys

FFT-fliken är implementerad som en självständig funktion. Användaren kan:

- Välja en eller flera WAV-, MP3- eller FLAC-filer, eller en hel mapp, och klicka på en fil i listan för att analysera den.
- Ange ett tonnamn, exempelvis `A4`, och instrument, exempelvis `guitar`.
- Beräkna en ensidig FFT över hela ljudsignalen.
- Visa frekvens på x-axeln och amplitud i dB på y-axeln.
- Normalisera spektrumet så att den starkaste toppen visas som 0 dB.
- Visa och exportera frekvensområdet 0 till 5000 Hz.
- Spara både diagrammet som PNG och frekvens/amplitud-paren som CSV.
- Analysera och spara PNG och CSV för alla filer i listan på en gång med **Analyze and save all** (filnamnet används som tonnamn).
- Zooma och panorera i diagrammet, markera flera datapunkter och spara urvalet som CSV.

FFT:n använder ett Hann-fönster för att minska läckage från signalens ändpunkter. En fönsterkorrigering används före amplitudberäkningen. Det starkaste synliga FFT-värdet normaliseras till 0 dB, och övriga värden visas relativt toppen. Resultatet sparas i `data/fft_results/` med tonnamn, instrument och tidsstämpel i filnamnet. Filer från en undermapp, till exempel `data/raw_audio/Eriks gitarr/`, sparas i `data/fft_results/Eriks gitarr/`. Om samplingsfrekvensen ger en lägre Nyquistfrekvens än 5000 Hz används den lägre gränsen automatiskt.

### 4. Lagerjämförelse

Lagerjämförelsefliken är implementerad och arbetar med CSV-filerna från FFT-fliken. Användaren kan:

- Lägga till flera sparade FFT-resultat samtidigt, eller alla CSV-filer i en mapp med **Add folder…**. Nya filer läggs till bland de lager som redan finns, så att resultat från olika mappar (till exempel olika instrument) kan jämföras. Har två filer samma namn visas mappnamnet framför.
- Visa eller dölja alla lager på en gång med **Show all** och **Hide all**.
- Visa kurvorna överlagrade i samma diagram.
- Slå av och på varje lager med en individuell checkbox.
- Se en legend med lagrens filnamn (döljs när fler än 20 lager visas samtidigt, eftersom den annars täcker diagrammet).
- Zooma och panorera, markera datapunkter från flera lager och spara urvalet som CSV.
- Exportera de synliga lagren som en ny PNG-fil.

Lagren visas med kontrasterande färger och lätt transparens inom 0-5000 Hz. Exporterna sparas i `data/layered_exports/` med tidsstämpel i filnamnet.

## Teknisk struktur

```text
project_root/
├── main.py
├── README.md
├── requirements.txt
├── gui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── note_recorder_tab.py
│   ├── noise_reduction_tab.py
│   ├── fft_analysis_tab.py
│   └── layer_comparison_tab.py
├── core/
│   ├── __init__.py
│   ├── audio_io.py
│   ├── note_recording.py
│   ├── noise_reduction.py
│   ├── fft_processing.py
│   └── layer_export.py
├── tests/
│   └── test_note_recording.py
└── data/
	├── raw_audio/
	├── cleaned_audio/
	├── fft_results/
	└── layered_exports/
```

### Ansvarsfördelning

- `main.py`: startar QApplication och huvudfönstret.
- `gui/main_window.py`: skapar huvudfönstret, de fyra flikarna och datamapparna.
- `gui/note_recorder_tab.py`: gränssnitt för guidad inspelning av enskilda toner.
- `gui/noise_reduction_tab.py`: gränssnitt för ljudval, förhandsvisning och sparande.
- `gui/fft_analysis_tab.py`: gränssnitt för FFT-analys och export.
- `gui/layer_comparison_tab.py`: gränssnitt för att välja, toggla och exportera FFT-lager.
- `core/audio_io.py`: läser ljudfiler och sparar WAV-filer.
- `core/note_recording.py`: tonlistor, detektering av anslag och tystnad, klippning och FLAC-export.
- `core/noise_reduction.py`: innehåller den spektrala brusreduceringen.
- `core/fft_processing.py`: FFT-beräkning samt PNG- och CSV-export.
- `core/layer_export.py`: läser FFT-CSV-filer och sparar överlagrade PNG-grafer.

## Installation

Projektet är avsett för Python 3.10 eller senare. På Windows kan den lokala virtuella miljön skapas och aktiveras så här:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Om PowerShell hindrar aktivering i den aktuella terminalen kan den här inställningen användas tillfälligt för processen:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
```

Det går även att köra programmets Python direkt utan att aktivera miljön:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Starta programmet

Från projektroten körs:

```powershell
.\venv\Scripts\python.exe main.py
```

Vid programstart skapas följande mappar automatiskt om de saknas:

- `data/raw_audio/`: originalinspelningar som användaren vill analysera.
- `data/cleaned_audio/`: sparade brusreducerade WAV-filer.
- `data/fft_results/`: PNG- och CSV-resultat från FFT-analysen.
- `data/layered_exports/`: exporter från lagerjämförelsen.

## Använd toninspelningen

1. Starta programmet och öppna fliken `Note recorder`.
2. Välj instrument och, för piano eller eget instrument, lägsta och högsta ton.
3. Välj mikrofon och skriv ett mappnamn, exempelvis `Eriks gitarr`.
4. Var tyst och klicka på `Measure noise` så att tröskeln ställs in. Den röda linjen i nivåmätaren visar tröskeln.
5. Klicka på `Start session` och spela tonen som visas.
6. När det står `Saved ✓`: tryck mellanslag för nästa ton, `R` för att ta om eller `L` för att lyssna. `Skip` hoppar över en ton.

Tips: dämpa strängen eller släpp tangenten innan du trycker mellanslag, så att nästa inspelning inte startar av den förra tonen. Höj `Max length per note` för långa pianotoner i basen.

## Använd brusreduceringen

1. Starta programmet.
2. Öppna fliken `Noise reduction`.
3. Klicka på `Select audio file`.
4. Välj en WAV-, MP3- eller FLAC-fil. Originalinspelningar kan exempelvis ligga i `data/raw_audio/`.
5. Kontrollera före- och efterkurvorna i spektrumdiagrammet.
6. Klicka på `Reduce noise and save` när resultatet är rimligt.
7. Den nya filen sparas i `data/cleaned_audio/` med tidsstämpel i filnamnet.

Diagrammet visar hela det analyserade frekvensområdet i brusreduceringsfliken. Begränsningen till 0-5000 Hz gäller den separata FFT-analysen, inte brusreduceringens preview.

## Använd FFT-analysen

1. Starta programmet.
2. Öppna fliken `FFT analysis`.
3. Klicka på `Select audio file` och välj en WAV-, MP3- eller FLAC-fil.
4. Ange tonnamn och instrument för ett tydligt filnamn.
5. Klicka på `Analyze FFT`.
6. Kontrollera spektrumet mellan 0 och 5000 Hz; den starkaste toppen är 0 dB.
7. Använd diagramverktygen för att zooma eller panorera. Klicka på kurvpunkter för att markera dem och välj `Save selected points` för att exportera urvalet separat.
8. Klicka på `Save PNG and CSV`.

Två filer sparas i `data/fft_results/`: en PNG-bild och en CSV-fil med kolumnerna `frequency_hz` och `amplitude_db`. CSV-filen är den rådata som senare ska användas av lagerjämförelsen.

## Använd lagerjämförelsen

1. Skapa och spara minst två FFT-resultat från fliken `FFT analysis`.
2. Öppna fliken `Layer comparison`.
3. Klicka på `Select FFT CSV files`.
4. Markera en eller flera CSV-filer i `data/fft_results/`.
5. Använd checkboxarna för att slå av eller på enskilda kurvor.
6. Zooma eller panorera och klicka på kurvpunkter för att markera punkter från olika lager. Välj `Save selected points` för att exportera urvalet med lagernamn.
7. Klicka på `Export layered PNG` för att spara den synliga jämförelsen.

Den exporterade bilden sparas i `data/layered_exports/`. `Clear layers` tömmer den aktuella jämförelsen så att en ny uppsättning filer kan väljas.

## Testning

Kompilera alla Python-moduler:

```powershell
.\venv\Scripts\python.exe -m compileall -q main.py gui core
```

Kör enhetstesterna för toninspelningen:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```

Den första signaltesten använder en syntetisk signal med 440 Hz och 880 Hz samt tillagt brus. Den kontrollerar att:

- den behandlade signalen har samma längd som originalet,
- brusreduceringen sänker den totala energin,
- de tydliga tonkomponenterna fortfarande finns kvar efter behandlingen.

Det finns ännu ingen komplett automatiserad testsvit. Nästa teststeg är tester för olika brusnivåer, samplingsfrekvenser och riktiga inspelningar.

## Roadmap

### Etapp 1: Projektgrund

- [x] Skapa Python-projektets mappstruktur.
- [x] Skapa startfilen `main.py`.
- [x] Skapa ett lokalt PySide6-fönster.
- [x] Skapa tre oberoende flikar.
- [x] Skapa `data/`-mappstrukturen automatiskt vid start.
- [x] Lägga till beroenden i `requirements.txt`.

### Etapp 2: Brusreducering

- [x] Läsa WAV, MP3 och FLAC.
- [x] Behålla originalets samplingsfrekvens vid inläsning.
- [x] Implementera STFT-baserad brusprofil.
- [x] Implementera mjuk spektral mask.
- [x] Skydda lokalt tydliga tonala toppar.
- [x] Visa före- och efter-spektrum.
- [x] Spara resultatet som tidsstämplad WAV.
- [x] Testa signalens längd och harmoniska bevaring med syntetisk signal.
- [ ] Utvärdera algoritmen på flera riktiga inspelningar.
- [ ] Göra brusparametrar justerbara i gränssnittet.

### Etapp 3: FFT-analys

- [x] Implementera FFT-beräkning i `core/fft_processing.py`.
- [x] Bygga filväljare och analysknapp i FFT-fliken.
- [x] Visa frekvensområdet 0-5000 Hz.
- [x] Visa amplitud på logaritmisk dB-skala.
- [ ] Lägga till val av hela signalen eller ett tidsutsnitt.
- [x] Spara graf som PNG.
- [x] Spara frekvens/amplitud som CSV eller JSON.
- [x] Använda tydliga filnamn med ton, instrument och tidsstämpel.

### Etapp 4: Lagerjämförelse

- [x] Implementera laddning av sparade FFT-resultat.
- [x] Visa flera spektrum som överlagrade kurvor.
- [x] Ge varje lager en egen färg och legendtext.
- [x] Lägga till av/på-kontroll för varje lager.
- [x] Exportera den sammanslagna vyn som PNG.
- [x] Spara exporter i `data/layered_exports/`.

### Etapp 5: Kvalitet och rapportunderlag

- [ ] Lägga till automatiserade enhetstester för core-funktionerna.
- [ ] Testa olika samplingsfrekvenser och korta ljudfiler.
- [ ] Testa felmeddelanden för korrupta och tomma ljudfiler.
- [ ] Dokumentera metod, parametrar och begränsningar i gymnasiearbetet.
- [ ] Göra ett reproducerbart testprotokoll för jämförelser mellan instrument.
- [ ] Kontrollera paketering och distribution som fristående desktopprogram.

## Begränsningar just nu

- FFT-analysen arbetar över hela signalen; tidsutsnitt är ännu inte implementerat.
- Lagerjämförelsen kräver att CSV-filer först skapas via FFT-fliken.
- Brusreduceringen antar i praktiken att delar av inspelningen representerar bakgrundsbrus.
- En mycket svag eller konstant ton kan påverka uppskattningen av brusgolvet.
- MP3-avkodning kräver att alla ljudberoenden i `requirements.txt` är korrekt installerade.
- Programmet är ännu inte paketerat som en installerbar `.exe`.

## Licens och källor

Detta repository är ett skolprojekt. Licens och eventuella externa källhänvisningar kompletteras när projektets rapport och distributionsform är fastställda.