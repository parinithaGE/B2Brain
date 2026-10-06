"""Streamlit frontend and application entry point."""

import asyncio
import html

import streamlit as st

from app.assistant import B2BDocumentationAssistant


st.set_page_config(
    page_title="B2B Documentation Assistant",
    page_icon="📚",
    layout="wide",
)


st.markdown(
    """
    <style>
        .block-container {
            max-width: 1180px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        .app-title {
            text-align: center;
            margin-bottom: 2rem;
        }

        .app-title h1 {
            font-size: 2.4rem;
            margin: 0;
        }

        .answer-box {
            padding: 1.25rem;
            border-radius: 14px;
            border: 1px solid rgba(45, 150, 105, 0.30);
            background: rgba(45, 150, 105, 0.08);
            line-height: 1.65;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def run_pipeline(question: str) -> dict:
    """Run the existing asynchronous documentation pipeline."""

    assistant = B2BDocumentationAssistant()

    return asyncio.run(
        assistant.run(question)
    )


def display_answer(answer: str) -> None:
    """Display only the generated answer."""

    if not answer:
        st.warning(
            "No answer was generated."
        )
        return

    escaped_answer = html.escape(
        answer
    ).replace(
        "\n",
        "<br>",
    )

    st.markdown(
        f'<div class="answer-box">{escaped_answer}</div>',
        unsafe_allow_html=True,
    )


def display_result(result: dict) -> None:
    """Display only the final answer in Streamlit."""

    if result.get("error"):
        st.error(
            result["error"]
        )
        return

    display_answer(
        result.get(
            "answer",
            "",
        )
    )


if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


st.markdown(
    """
    <div class="app-title">
        <h1>📚 B2B Documentation Assistant</h1>
    </div>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------
# Existing conversation
# --------------------------------------------------------------

for message in st.session_state.chat_history:

    with st.chat_message("user"):
        st.markdown(
            message["question"]
        )

    with st.chat_message("assistant"):
        display_result(
            message["result"]
        )


# --------------------------------------------------------------
# New question
# --------------------------------------------------------------

question = st.chat_input(
    "Ask your Microsoft B2B documentation question..."
)


if question is not None:

    question = question.strip()

    if not question:

        st.warning(
            "Please enter a question."
        )

    else:

        with st.chat_message("user"):
            st.markdown(
                question
            )

        with st.chat_message("assistant"):

            with st.spinner(
                "Searching documentation and generating answer..."
            ):

                try:

                    result = run_pipeline(
                        question
                    )

                except Exception as exc:

                    result = {
                        "error": str(exc),
                        "answer": "",
                    }

            display_result(
                result
            )

        st.session_state.chat_history.append(
            {
                "question": question,
                "result": result,
            }
        )
        