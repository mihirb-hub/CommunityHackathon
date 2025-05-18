import { GoogleGenerativeAI, HarmBlockThreshold, HarmCategory } from '@google/generative-ai'
import MarkdownIt from 'markdown-it'
import { maybeShowApiKeyBanner } from './gemini-api-banner'
import './style.css'

// Your Gemini key
const API_KEY = 'YOUR_API_KEY'

// The hidden, uneditable prompt
const USER_PROMPT = 
  "Give 5–25 keywords about this image, each starting with #, and no other information. Here are some examples that should give you a sense of what kind of words I want. #performance #audience #instruments #event #public #audience #percussion instruments #banquet #performance #singing #OAA event #celebration#event #banquet #dinner party #formal event #photograph #cameras #dinner party #performance #makeup #dance #theater #dress #instruments#event #outdoor event #parade #Little Tokyo #Los Angeles #Nisei Week #Nisei #Nisei Grand Parade #Nikkei Parents of the Year Clarance #Helen Nishizu National Parents Day #Ito Farms #Tony Okada #Jim Woole #Akira Fukuda #Pan-Olympic Games #Olympics #karate #judo #Sumi Onodera-Leonard #Arthur Mokane #Maito #Daiko Matsuri Ryukyukoku #banners #instruments #performance #martial arts #float #beauty queen #costume #Mexico #Native American #Trudy Nodohara #Little Tokyo Lion's Club #Lion's Club #dance. for each i do not want you to say here are some keywords"

const form      = document.querySelector('form')
const fileInput = document.getElementById('fileInput')
const output    = document.querySelector('.output')

form.addEventListener('submit', async (ev) => {
  ev.preventDefault()
  output.innerHTML = ''              // clear old results

  if (!fileInput.files.length) {
    output.innerHTML = `<div style="color:red">Please select at least one image.</div>`
    return
  }

  // we'll accumulate here
  const allResults = []

  // Process each selected file sequentially
  for (const file of fileInput.files) {
    // make a container per-file
    const container = document.createElement('div')
    container.className = 'result'
    output.appendChild(container)

    // show filename
    const title = document.createElement('h3')
    title.textContent = file.name
    container.appendChild(title)

    // placeholder
    const resultDiv = document.createElement('p')
    resultDiv.textContent = 'Generating…'
    container.appendChild(resultDiv)

    try {
      // 1) load & b64 encode
      const imageBase64 = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.readAsDataURL(file)
        reader.onload = () => resolve(reader.result.split(',')[1])
        reader.onerror = reject
      })

      // 2) build payload
      const contents = [{
        role: 'user',
        parts: [
          { inline_data: { mime_type: file.type, data: imageBase64 }},
          { text: USER_PROMPT }
        ]
      }]

      // 3) call Gemini
      const genAI = new GoogleGenerativeAI(API_KEY)
      const model = genAI.getGenerativeModel({
        model: 'gemini-1.5-flash',
        safetySettings: [{
          category: HarmCategory.HARM_CATEGORY_HARASSMENT,
          threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }],
      })
      const response = await model.generateContentStream({ contents })

      // 4) stream & render
      const md     = new MarkdownIt()
      const buffer = []
      for await (const chunk of response.stream) {
        buffer.push(chunk.text())
        resultDiv.innerHTML = md.render(buffer.join(''))
      }

      // 5) extract the raw hashtags as an array
      const hashtags = buffer.join('')
      // split on spaces (since we prefix each with #)
      const parts = hashtags
        .split(/\s+/)
        .filter(tok => tok.startsWith('#'))

      // store in allResults
      allResults.push({
        file: file.name,
        keywords: parts
      })
    } catch (e) {
      resultDiv.innerHTML = `<span style="color:red">Error: ${e.message || e}</span>`
    }
  }

  // once everything is done, offer JSON download:
  const blob   = new Blob([JSON.stringify(allResults, null, 2)], {
    type: 'application/json'
  })
  const url    = URL.createObjectURL(blob)
  const dlLink = document.createElement('a')
  dlLink.href     = url
  dlLink.download = 'keywords.json'
  dlLink.textContent = 'Download keywords as JSON'
  dlLink.style.display = 'block'
  dlLink.style.marginTop = '1rem'
  output.appendChild(dlLink)
})

// show API‐key banner if needed
maybeShowApiKeyBanner(API_KEY)
