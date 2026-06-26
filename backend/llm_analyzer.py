import os
import json
import requests
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"

def get_groq_api_key():
    return os.environ.get("GROQ_API_KEY", "")

def call_groq_api(messages, json_mode=False):
    api_key = get_groq_api_key()
    if not api_key:
        return {"error": "Groq API key not configured. Please add it to your environment."}
        
    payload = {
        "model": DEFAULT_MODEL,
        "messages": messages,
        "temperature": 0.3 if json_mode else 0.7,
        "max_tokens": 1500,
    }
    
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=25)
        if response.status_code == 401:
            return {"error": "Invalid Groq API key. Check settings."}
        elif response.status_code != 200:
            return {"error": f"Groq API returned error status {response.status_code}: {response.text[:200]}"}
            
        data = response.json()
        return {"content": data["choices"][0]["message"]["content"]}
    except Exception as e:
        return {"error": f"Failed to connect to Groq: {str(e)}"}

def analyze_article(title, category, source, full_text=None):
    """
    Analyzes an article title and optionally full text to infer details, financial implications, and PI interview questions.
    Returns a dictionary with summary, implications, and pi_questions.
    """
    system_prompt = (
        "You are an elite finance professor and a veteran interviewer for the Master in Finance (MFin) course at JBIMS. "
        "Your task is to analyze the provided news content and generate a comprehensive prep card for candidates. "
        "Generate a JSON object. You must strictly follow this JSON format:\n"
        "{\n"
        '  "summary": "A precise, one-sentence explanation of the news event, its context, and who is involved.",\n'
        '  "implications": [\n'
        '    "Implication 1: Details the economic impact (inflation, interest rates, currency, fiscal deficit, GDP, etc.) or corporate impact.",\n'
        '    "Implication 2: Details the financial markets impact (nifty/sensex, bond yields, equity valuations, sector performance).",\n'
        '    "Implication 3: Details the banking, policy, or credit market impact."\n'
        '  ],\n'
        '  "pi_questions": [\n'
        "    {\n"
        '      "question": "A sharp, analytical question an MFin interviewer could ask a candidate (e.g. \'If interest rates are rising, how will that affect bank NIMs vs valuation?\').",\n'
        '      "sample_answer": "A complete, well-structured sample answer (3-5 sentences) that a top MFin candidate would give in a personal interview. Use precise financial terminology, mention relevant economic theories or models, reference specific metrics or indicators, and demonstrate strong analytical reasoning. Write it in first person as if the candidate is speaking to the interview panel. Example: \'Rising interest rates have a dual impact on the banking sector. On one hand, bank Net Interest Margins (NIMs) expand as the spread between lending and deposit rates widens, particularly benefiting banks with a higher share of CASA deposits. However, this is offset by potential deterioration in asset quality as borrowers face higher EMI burdens, leading to increased NPAs. From a valuation perspective, higher rates compress P/E multiples due to a rising risk-free rate, which reduces the present value of future earnings.\'"\n'
        "    },\n"
        "    {\n"
        '      "question": "A macro or conceptual question related to this news (e.g., testing understanding of fiscal policy, trade balances, or corporate finance).",\n'
        '      "sample_answer": "A complete, well-structured sample answer (3-5 sentences) demonstrating deep knowledge of economics and finance. Use relevant theories (e.g., Mundell-Fleming model, IS-LM framework, twin deficit hypothesis), reference real-world data or recent policy decisions, and connect micro-level impacts to macro-level outcomes. Write it in first person as if the candidate is answering the interview panel."\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    
    context_text = f"Title: {title}\nCategory: {category}\nSource: {source}\n"
    if full_text:
        # Cap full text to 1000 words to avoid exceeding context
        cap_words = " ".join(full_text.split()[:1000])
        context_text += f"Article Content:\n{cap_words}\n"
        
    user_prompt = f"{context_text}\n\nAnalyze this news article and generate the MFin PI Prep Card."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    result = call_groq_api(messages, json_mode=True)
    if "error" in result:
        return result
        
    try:
        parsed = json.loads(result["content"])
        return parsed
    except Exception as e:
        return {"error": f"Failed to parse JSON response: {str(e)}", "raw_content": result.get("content")}

def generate_daily_briefing(articles_summary):
    """
    Generates a daily digest email/newsletter style briefing based on top headlines.
    articles_summary is a list of dictionaries with title, category, and source.
    """
    if not articles_summary:
        return "No fresh news articles found to compile today's briefing. Please fetch news first."
        
    articles_text = "\n".join([
        f"- [{a['category']}] {a['title']} (Source: {a['source']})"
        for a in articles_summary[:8]
    ])
    
    system_prompt = (
        "You are an expert financial journalist and MFin advisor. "
        "Compile a sophisticated, engaging, and professional business briefing (similar to the Financial Times or Morning Brew) "
        "tailored specifically for JBIMS Master in Finance candidates preparing for their interviews.\n\n"
        "Structure your response in Markdown with these specific sections:\n"
        "1. ## Executive Summary: A 3-sentence macro overview of the day's dominant themes.\n"
        "2. ## Core Themes: Group the news into 2-3 logical themes (e.g., 'Monetary Policy & Inflation', 'Market Dynamics', 'Geopolitical Headwinds'). For each theme, explain the narrative, connect the headlines, and describe the broader economic mechanism at play.\n"
        "3. ## MFin Buzzwords to Know: List 3-4 advanced financial/economic terms relevant to today's news and define them in a single, crisp sentence each.\n"
        "4. ## Interview Hot-Seat Tip: A strategic tip on how to handle questions about these topics in a personal interview (e.g., 'If asked about the Fed rate hike, always pivot to its impact on emerging market capital outflows and the Rupee')."
    )
    
    user_prompt = f"Today's Headlines:\n{articles_text}\n\nCompile today's MFin Daily Briefing."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    result = call_groq_api(messages, json_mode=False)
    if "error" in result:
        return result["error"]
        
    return result["content"]

def conduct_mock_interview(chat_history, today_news_headlines):
    """
    Manages the MFin PI interview chatbot flow.
    chat_history: list of dicts: [{'role': 'panelist'|'candidate', 'content': '...'}]
    today_news_headlines: list of strings (headlines from today to seed the interview)
    
    Flow:
    - If history is empty: Panelist introduces themselves, mentions they'll ask 3 questions about today's business environment, and poses Question 1.
    - If 1 question answered (history length 2): Panelist gives feedback on answer 1 and poses Question 2.
    - If 2 questions answered (history length 4): Panelist gives feedback on answer 2 and poses Question 3.
    - If 3 questions answered (history length 6): Panelist evaluates answer 3, declares the interview finished, and provides a structured evaluation report (Score, Strengths, Gaps, Model Answers).
    
    Returns a dict: {'response': 'Next panelist utterance', 'score': int (only on final step), 'completed': bool}
    """
    num_answers = sum(1 for msg in chat_history if msg.get("role") == "candidate")
    
    # Format headlines for context
    headlines_context = "\n".join(today_news_headlines[:6])
    
    system_prompt = (
        "You are the Chairperson of the In-Person Assessment Panel for the Master in Finance (MFin) course at JBIMS. "
        "Your interviewing style is rigorous, highly analytical, academic, and professional. "
        "You test candidates on current affairs, economic theory, and market dynamics, and expect them to use precise finance terms.\n\n"
        "Rules:\n"
        "- Keep your replies focused, crisp, and under 150 words during the active interview.\n"
        "- Do not use greeting phrases on every turn. Be conversational but formal.\n"
        "- The interview covers exactly 3 questions.\n"
        "- Question themes must relate directly to today's business headlines: \n"
        f"{headlines_context}\n\n"
        "Phase-based instructions:\n"
        "1. **Start (no history)**: Welcome the candidate warmly. State that the interview will test their understanding of today's finance, market, and geopolitical landscape. Ask the FIRST question based on one of the headlines.\n"
        "2. **Follow-ups (turns 2 & 4)**: Briefly critique the candidate's answer (point out what was strong or what was missing, e.g. 'Good explanation of equity risk premium, but you did not mention its impact on liquidity'). Then ask the NEXT question (Question 2 or 3) on a different topic from the headlines.\n"
        "3. **Conclusion (turn 6)**: Evaluate their final answer. Then, declare the interview completed. Provide a comprehensive MFin PI Evaluation Report. You must output the report in Markdown, including: \n"
        "   - **Score**: [A number between 0 and 100]\n"
        "   - **Strengths**: [2 points about their expression, vocabulary, or economic logic]\n"
        "   - **Development Areas**: [2 concepts or metrics they should research further to sound more polished]\n"
        "   - **PI Model Answer Pointers**: [Brief bullet points on how to perfectly tackle the 3 questions asked]\n"
        "   - To ensure the frontend parses the score, please wrap the final score in a special token: [SCORE]XX[/SCORE] (e.g. [SCORE]85[/SCORE])."
    )
    
    # Convert chat history to API format
    api_messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history:
        role = "assistant" if msg["role"] == "panelist" else "user"
        api_messages.append({"role": role, "content": msg["content"]})
        
    # Ask the API
    result = call_groq_api(api_messages, json_mode=False)
    if "error" in result:
        return {"response": f"Panelist offline: {result['error']}", "completed": False}
        
    response_text = result["content"]
    
    # Determine completion
    completed = num_answers >= 3
    score = None
    
    if completed:
        # Extract score from [SCORE]XX[/SCORE]
        import re
        match = re.search(r"\[SCORE\](\d+)\[/SCORE\]", response_text)
        if match:
            score = int(match.group(1))
            # Clean up token from display
            response_text = response_text.replace(match.group(0), f"**Overall MFin PI Score: {score}/100**")
        else:
            score = 75  # Fallback
            
    return {
        "response": response_text,
        "score": score,
        "completed": completed
    }
