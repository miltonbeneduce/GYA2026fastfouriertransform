# Tone Spectrum Analyzer

Ett lokalt skrivbordsprogram i Python för att analysera och jämföra klangspektra från inspelade toner. Projektet är en del av ett gymnasiearbete inom ljudanalys.

Programmet är tänkt att användas för att jämföra exempelvis samma ton spelad på olika gitarrer eller pianon. Målet är att kunna se grundtoner, övertoner och undertoner i frekvensdomänen utan att förlora den harmoniska strukturen vid brusreducering.

## Projektstatus

Projektet byggs stegvis. Följande delar är klara just nu:

- [x] Körbart lokalt PySide6-program
- [x] Huvudfönster med tre separata flikar
- [x] Automatisk skapning av programmets datamappar
- [x] Ljudinläsning för WAV, MP3 och FLAC
- [x] Spektral brusreducering med STFT
- [x] Före- och eftervisning av spektrum i brusreduceringsfliken
- [x] Sparande av brusreducerad ljudfil som WAV
- [x] Grundläggande kontrolltest av harmonisk bevaring
- [ ] Fullständig FFT-analysflik
- [ ] Sparande av FFT-grafer och rådata
- [ ] Lagerjämförelse av flera FFT-resultat
- [ ] Av/på-kontroller för enskilda lager
- [ ] Export av sammanslagna lagergrafer
- [ ] Mer omfattande tester med riktiga inspelningar

## Funktioner

### 1. Brusreducering

Brusreduceringen är den första färdigbyggda funktionen. Användaren kan:

1. Välja en ljudfil via en filväljardialog.
2. Läsa in filen som en monosignal utan att ändra samplingsfrekvensen.
3. Visa ett spektrum före och efter brusreduceringen.
4. Spara den behandlade signalen som en ny WAV-fil.

Brusreduceringen använder inte ett enkelt lågpassfilter. Ett lågpassfilter skulle kunna ta bort höga övertoner även om de tillhör själva tonen. I stället används en försiktig spektral gate:

- Signalen delas upp i tids- och frekvensfönster med STFT.
- De tystaste 20 procenten av fönstren används för att uppskatta brusgolvet.
- Frekvenskomponenter nära brusgolvet dämpas med en mjuk mask.
- En maskgolvnivå på 20 procent förhindrar hård bortklippning.
- Lokalt tydliga spektrala toppar skyddas för att bevara grundtoner och övertoner.
- Masken jämnas försiktigt ut för att minska risken för så kallat musikaliskt brus.

Algoritmen kan fortfarande behöva finjusteras för olika typer av inspelningar. Särskilt varierande eller icke-stationärt brus bör testas med riktiga ljudfiler innan slutliga slutsatser dras i rapporten.

### 2. FFT-analys

FFT-fliken finns i huvudfönstret som en separat placeholder, men själva funktionen är ännu inte implementerad. Den planerade funktionen ska:

- Läsa in en inspelad enskild ton.
- Beräkna FFT över hela signalen eller ett valt utsnitt.
- Visa frekvens på x-axeln och amplitud i dB på y-axeln.
- Fokusera visningen på 0 till 5000 Hz.
- Spara grafen som PNG.
- Spara frekvens- och amplitudpar som CSV eller JSON.

### 3. Lagerjämförelse

Lagerjämförelsefliken finns också som en separat placeholder. Den planerade funktionen ska läsa sparade FFT-resultat, rita flera kurvor i samma diagram och ge varje lager en egen färg. Användaren ska kunna slå av och på individuella lager samt exportera den sammanslagna grafen som PNG.

## Teknisk struktur

```text
project_root/
├── main.py
├── README.md
├── requirements.txt
├── gui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── noise_reduction_tab.py
│   ├── fft_analysis_tab.py
│   └── layer_comparison_tab.py
├── core/
│   ├── __init__.py
│   ├── audio_io.py
│   ├── noise_reduction.py
│   ├── fft_processing.py
│   └── layer_export.py
└── data/
	├── raw_audio/
	├── cleaned_audio/
	├── fft_results/
	└── layered_exports/
```

### Ansvarsfördelning

- `main.py`: startar QApplication och huvudfönstret.
- `gui/main_window.py`: skapar huvudfönstret, de tre flikarna och datamapparna.
- `gui/noise_reduction_tab.py`: gränssnitt för ljudval, förhandsvisning och sparande.
- `gui/fft_analysis_tab.py`: reserverad för FFT-analys.
- `gui/layer_comparison_tab.py`: reserverad för lagerjämförelse.
- `core/audio_io.py`: läser ljudfiler och sparar WAV-filer.
- `core/noise_reduction.py`: innehåller den spektrala brusreduceringen.
- `core/fft_processing.py`: reserverad för gemensamma FFT-funktioner.
- `core/layer_export.py`: reserverad för lagring och export av jämförelser.

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
- `data/fft_results/`: framtida PNG- och CSV/JSON-resultat från FFT-analysen.
- `data/layered_exports/`: framtida exporter från lagerjämförelsen.

## Använd brusreduceringen

1. Starta programmet.
2. Öppna fliken `Noise reduction`.
3. Klicka på `Select audio file`.
4. Välj en WAV-, MP3- eller FLAC-fil. Originalinspelningar kan exempelvis ligga i `data/raw_audio/`.
5. Kontrollera före- och efterkurvorna i spektrumdiagrammet.
6. Klicka på `Reduce noise and save` när resultatet är rimligt.
7. Den nya filen sparas i `data/cleaned_audio/` med tidsstämpel i filnamnet.

Diagrammet visar hela det analyserade frekvensområdet i brusreduceringsfliken. Begränsningen till 0-5000 Hz hör till den framtida separata FFT-analysen, inte till brusreduceringens preview.

## Testning

Kompilera alla Python-moduler:

```powershell
.\venv\Scripts\python.exe -m compileall -q main.py gui core
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

- [ ] Implementera FFT-beräkning i `core/fft_processing.py`.
- [ ] Bygga filväljare och analysknapp i FFT-fliken.
- [ ] Visa frekvensområdet 0-5000 Hz.
- [ ] Visa amplitud på logaritmisk dB-skala.
- [ ] Lägga till val av hela signalen eller ett tidsutsnitt.
- [ ] Spara graf som PNG.
- [ ] Spara frekvens/amplitud som CSV eller JSON.
- [ ] Använda tydliga filnamn med ton, instrument och tidsstämpel.

### Etapp 4: Lagerjämförelse

- [ ] Implementera laddning av sparade FFT-resultat.
- [ ] Visa flera spektrum som överlagrade kurvor.
- [ ] Ge varje lager en egen färg och legendtext.
- [ ] Lägga till av/på-kontroll för varje lager.
- [ ] Exportera den sammanslagna vyn som PNG.
- [ ] Spara exporter i `data/layered_exports/`.

### Etapp 5: Kvalitet och rapportunderlag

- [ ] Lägga till automatiserade enhetstester för core-funktionerna.
- [ ] Testa olika samplingsfrekvenser och korta ljudfiler.
- [ ] Testa felmeddelanden för korrupta och tomma ljudfiler.
- [ ] Dokumentera metod, parametrar och begränsningar i gymnasiearbetet.
- [ ] Göra ett reproducerbart testprotokoll för jämförelser mellan instrument.
- [ ] Kontrollera paketering och distribution som fristående desktopprogram.

## Begränsningar just nu

- FFT- och lagerflikarna är ännu inte funktionella.
- `core/fft_processing.py` och `core/layer_export.py` innehåller ännu inga implementationer.
- Brusreduceringen antar i praktiken att delar av inspelningen representerar bakgrundsbrus.
- En mycket svag eller konstant ton kan påverka uppskattningen av brusgolvet.
- MP3-avkodning kräver att alla ljudberoenden i `requirements.txt` är korrekt installerade.
- Programmet är ännu inte paketerat som en installerbar `.exe`.

## Licens och källor

Detta repository är ett skolprojekt. Licens och eventuella externa källhänvisningar kompletteras när projektets rapport och distributionsform är fastställda.