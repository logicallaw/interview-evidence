# Interview Evidence: Find Interview Answers Worth Revisiting

Interview Evidence is a local web app that transcribes interview audio with the RTZR Batch STT API and runs `google/embeddinggemma-300m` locally to retrieve candidate responses that are semantically related to a review criterion. Reviewers can verify each result against its transcript context and source audio.

> Search results are suggestions for human review. The app does not evaluate or score candidates.

## 🎯 Goal

Interview Evidence helps interviewers quickly find candidate responses related to a specific evaluation criterion and review the transcript context and source audio as evidence for their assessment.

## ✨ Motivation

After an interview, locating evidence for a specific evaluation criterion in a long recording can be time-consuming. Interviewers need to find relevant responses and review their surrounding context before making an assessment. Keyword search may miss answers expressed in different words, while a transcript alone cannot convey the candidate's tone and delivery.

Interview Evidence combines speaker-aware transcription, semantic retrieval, transcript context, and source-audio playback to help interviewers find relevant responses and assess candidates based on supporting evidence.

## 🔑 Key Features

- Speaker-aware transcription of two-person interviews through the RTZR Batch STT API
- Semantic retrieval of up to three candidate responses related to an evaluation criterion
- Review of each answer with its transcript and preceding conversational context
- Source-audio playback from the start of the selected answer to three seconds after it ends
- Structured JSON export of the evaluation criterion and timestamped answer evidence for documentation and follow-up review

## 📺 Demo Video
Experience the functionality of this project by watching the demo video:  
[Watch the Demo](https://youtube.com/shorts/D9ucWfBXXJA?feature=share)

## 🚀 Quick Start

### Requirements

This project was developed and tested on macOS with Python 3.13.13.

All Python dependencies are pinned in [`requirements.txt`](requirements.txt).

Before you begin, make sure you have:

- An RTZR Developers application with its `RTZR_CLIENT_ID` and `RTZR_CLIENT_SECRET`
- A Hugging Face account with access to `google/embeddinggemma-300m` after accepting Google's usage license
- A Hugging Face access token, configured as `HF_TOKEN`, with permission to download the model

### 1. Clone the repository

```bash
git clone https://github.com/logicallaw/interview-evidence.git
cd interview-evidence
```

### 2. Create and activate a virtual environment

The following commands were tested on macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install the dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure the environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

Add your credentials to `.env`:

```dotenv
RTZR_CLIENT_ID=
RTZR_CLIENT_SECRET=
HF_TOKEN=
```

Do not commit the completed `.env` file.

### 5. Prepare EmbeddingGemma

`google/embeddinggemma-300m` is a gated model. Before running the preparation script, sign in to Hugging Face and accept the model's usage terms:

<https://huggingface.co/google/embeddinggemma-300m>

Then download and verify the model:

```bash
python scripts/prepare_model.py
```

### 6. Run the tests

This step is optional for running the app but recommended for verifying the installation:

```bash
python -m pytest
```

The default test suite does not require RTZR credentials, a Hugging Face token, or external API access.

### 7. Run the app

```bash
python -m streamlit run app.py
```

Streamlit will display the local URL in the terminal after the app starts.

## 🧪 Try It with the Sample Audio

The repository includes a synthetic two-person interview recording:

```text
public/audio/interview-sample.wav
```

The recording is approximately 9 minutes and 11 seconds long. It was created for demonstration purposes and contains no real interview data.

To verify the complete workflow:

1. Upload `public/audio/interview-sample.wav`.
2. Start the RTZR transcription.
3. Review the representative utterances for both speakers.
4. Select the speaker who represents the candidate.
5. Because the sample interview is in Korean, enter the following evaluation criterion:

   ```text
   높은 정확도가 실제 운영 성능으로 이어지지 않았을 때 원인을 어떻게 분석하고 개선했는가?
   ```

6. Review a result with `이 구간 듣기` (Listen to this segment) or `전사 문맥 보기` (View transcript context).
7. Download the results with `현재 검색 결과 내려받기` (Download current search results).

## ⚙️ How It Works

```text
Interview audio file (WAV)
  → Obtain an RTZR access token
  → Submit the audio for transcription and wait for completion
  → Review the speaker-labeled transcript and identify which speaker is the candidate
  → Group the candidate's consecutive utterances into answer segments
  → Enter an evaluation criterion
  → Compare the criterion with the candidate's answers
  → Present up to three answers closest in meaning to the criterion
  → Review the selected answer with its transcript context and source audio
  → Export the criterion, answers, and timestamps as structured JSON for follow-up review
```

The app obtains an RTZR access token, submits the WAV file to the Batch STT API, and polls the transcription job at a default interval of five seconds until it is completed. The resulting utterances are labeled by speaker so that the reviewer can identify which speaker is the candidate.

The candidate's consecutive utterances are grouped into answer segments. When the reviewer enters an evaluation criterion, the locally running `google/embeddinggemma-300m` model compares its meaning with the candidate's answers and returns up to three responses with the highest cosine similarity.

Each result can be reviewed with its transcript context and source audio. Audio playback starts at the beginning of the selected answer and continues until three seconds after it ends. The current criterion and timestamped answer evidence can then be exported as structured JSON for documentation and follow-up review.

## 📂 Project Structure

```bash
interview-evidence/
├── app.py                         # Streamlit UI and workflow orchestration
├── scripts/
│   └── prepare_model.py           # Downloads and verifies EmbeddingGemma
├── src/
│   ├── __init__.py
│   ├── exporters.py               # Builds the structured JSON export
│   ├── rtzr_client.py             # Handles RTZR authentication and transcription jobs
│   ├── segments.py                # Builds answer segments and playback boundaries
│   └── semantic_search.py         # Embeds text and retrieves the Top-K answers
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Shared pytest fixtures
│   ├── fixtures/
│   │   └── rtzr_completed.json    # Synthetic completed transcription response
│   ├── test_exporters.py
│   ├── test_integration.py
│   ├── test_rtzr_client.py
│   ├── test_segments.py
│   └── test_semantic_search.py
├── public/
│   └── audio/
│       └── interview-sample.wav   # Synthetic two-person interview audio
├── docs/
│   ├── ADR.md                     # Architecture decision records
│   ├── ARCHITECTURE.md            # System structure and data flow
│   ├── PRD.md                     # Product scope and requirements
│   └── UI_GUIDE.md                # UI states, copy, and visual guidelines
├── .github/
│   ├── ISSUE_TEMPLATE/            # Issue templates (bug, chore, docs, feature, fix)
│   └── pull_request_template.md   # Pull request template
├── .env.example                   # Environment variable template
├── .gitignore
├── requirements.txt               # Pinned Python dependencies
└── README.md
```

## ⚠️ Limitations

- The app processes one WAV file at a time.
- It is designed for interviews with exactly two detected speakers, and the reviewer must identify which speaker is the candidate.
- Only one evaluation criterion can be searched at a time.
- The app returns up to three results without applying an absolute relevance threshold, so each result should be reviewed in context.

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Architecture Decision Records](docs/ADR.md)
- [Product Requirements](docs/PRD.md)
- [UI Guide](docs/UI_GUIDE.md)

## 🎧 Sample Audio Attribution

The `public/audio/interview-sample.wav` file was generated with NAVER CLOVA Dubbing from an original script written by [logicallaw](https://github.com/logicallaw).

The recording is synthetic and does not contain real interview data. An audible attribution notice for NAVER CLOVA Dubbing is included at the beginning of the file.

## 📚 References and Attribution

This project was developed with reference to the following official documentation and examples:

- [RTZR Authentication Guide](https://developers.rtzr.ai/docs/authentications/) — access-token authentication
- [RTZR Batch STT API](https://developers.rtzr.ai/docs/stt-file/) — file upload, transcription polling, response fields, and STT options
- [RTZR Rate Limit](https://developers.rtzr.ai/docs/rate_limit/) — concurrency-limit handling and exponential backoff
- [EmbeddingGemma Model Overview](https://ai.google.dev/gemma/docs/embeddinggemma) — model characteristics and usage requirements
- [EmbeddingGemma with Sentence Transformers](https://ai.google.dev/gemma/docs/embeddinggemma/inference-embeddinggemma-with-sentence-transformers) — model loading and retrieval query/document prompts
- [RTZR Automatic Chapters Tutorial](https://blog.rtzr.ai/stt-api-auto-chapters-timestamps/) — conceptual reference during early exploration; the final project implements evaluation-criterion-based answer retrieval rather than automatic chapter segmentation

## 👥 Contributor

| Name                                                     | Role                   |
| -------------------------------------------------------- | ---------------------- |
| Kim Jun-Ho ([logicallaw](https://github.com/logicallaw)) | Full-stack AI engineer |

## 🧑‍💻 Contributing

1. Fork the repository and clone it locally.
2. Set up your development environment by following the [🚀 Quick Start](#-quick-start) section.
3. Create an issue for your change. Pick a template from `.github/ISSUE_TEMPLATE/` that matches the type of work.
4. Create a branch from main: `<type>/#<issue-number>-<slug>` (e.g. `fix/#16-playback`)
5. Follow the commit message format: `<type>(#<issue>/<scope>): description` (e.g. `fix(#16/segments): remove pre-playback offset`)
6. Run `python -m pytest` and make sure all tests pass.
7. Open a PR using `.github/pull_request_template.md` and include `Closes #N` in the body.

## 📝 Questions and Support

For questions or support:

- Open a GitHub issue
- Email: [logicallawbio@gmail.com](mailto:logicallawbio@gmail.com)
- GitHub: [logicallaw](https://github.com/logicallaw)
