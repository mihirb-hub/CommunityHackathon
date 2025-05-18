import { GoogleGenerativeAI, HarmBlockThreshold, HarmCategory } from '@google/generative-ai'
import MarkdownIt from 'markdown-it'
import { maybeShowApiKeyBanner } from './gemini-api-banner'
import './style.css'

// Your Gemini key
const API_KEY = 'AIzaSyCWcFxsgsyiMhGJeG0WOthIeIyrSyBpRIM'

// The hidden, uneditable prompt
const USER_PROMPT = 
  "Give 5–25 keywords about this image, each starting with #, and no other information. Here are some examples that should give you a sense of what kind of words I want. #performance #audience #instruments #event #public #audience #percussion instruments #banquet #performance #singing #OAA event #celebration#event #banquet #dinner party #formal event #photograph #cameras #dinner party #performance #makeup #dance #theater #dress #instruments#event #outdoor event #parade #Little Tokyo #Los Angeles #Nisei Week #Nisei #Nisei Grand Parade #Nikkei Parents of the Year Clarance #Helen Nishizu National Parents Day #Ito Farms #Tony Okada #Jim Woole #Akira Fukuda #Pan-Olympic Games #Olympics #karate #judo #Sumi Onodera-Leonard #Arthur Mokane #Maito #Daiko Matsuri Ryukyukoku #banners #instruments #performance #martial arts #float #beauty queen #costume #Mexico #Native American #Trudy Nodohara #Little Tokyo Lion's Club #Lion's Club #dance. for each i do not want you to say here are some keywords"

const form      = document.querySelector('form')
const fileInput = document.getElementById('fileInput')
const output    = document.querySelector('.output')

form.addEventListener('submit', async (ev) => {
  ev.preventDefault()
  output.innerHTML = ''              // clear any old results

  if (!fileInput.files.length) {
    output.innerHTML = `<div style="color:red">Please select at least one image.</div>`
    return
  }

  // Process each selected file, one after another
  for (const file of fileInput.files) {
    // Container for this file's result
    const container = document.createElement('div')
    container.className = 'result'
    output.appendChild(container)

    // Show filename
    const title = document.createElement('h3')
    title.textContent = file.name
    container.appendChild(title)

    // Placeholder while we generate
    const resultDiv = document.createElement('p')
    resultDiv.textContent = 'Generating…'
    container.appendChild(resultDiv)

    try {
      // 1) Read file into base64 (just the data part)
      const imageBase64 = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.readAsDataURL(file)
        reader.onload = () => {
          const b64 = reader.result.split(',')[1]
          resolve(b64)
        }
        reader.onerror = reject
      })

      // 2) Build multimodal payload
      const contents = [
        {
          role: 'user',
          parts: [
            { 
              inline_data: { 
                mime_type: file.type, 
                data: imageBase64 
              } 
            },
            { text: USER_PROMPT }
          ]
        }
      ]

      // 3) Call Gemini
      const genAI = new GoogleGenerativeAI(API_KEY)
      const model = genAI.getGenerativeModel({
        model: 'gemini-1.5-flash',
        safetySettings: [{
          category: HarmCategory.HARM_CATEGORY_HARASSMENT,
          threshold: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }],
      })
      const response = await model.generateContentStream({ contents })

      // 4) Stream and render markdown
      const md     = new MarkdownIt()
      const buffer = []
      for await (const chunk of response.stream) {
        buffer.push(chunk.text())
        resultDiv.innerHTML = md.render(buffer.join(''))
      }
    } catch (e) {
      resultDiv.innerHTML = `<span style="color:red">Error: ${e.message || e}</span>`
    }
  }
})

// show API‐key banner if needed
maybeShowApiKeyBanner(API_KEY)
