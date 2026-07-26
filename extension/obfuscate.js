// obfuscate.js – Ejecutar con Node.js para ofuscar los archivos JS
// npm install -g javascript-obfuscator
// node obfuscate.js

const fs = require('fs');
const path = require('path');
const JavaScriptObfuscator = require('javascript-obfuscator');

const files = ['popup.js', 'service_worker.js', 'content_script.js'];

files.forEach(file => {
    const filePath = path.join(__dirname, file);
    if (!fs.existsSync(filePath)) {
        console.warn(`⚠️ Archivo no encontrado: ${file}`);
        return;
    }
    const code = fs.readFileSync(filePath, 'utf8');
    const result = JavaScriptObfuscator.obfuscate(code, {
        compact: true,
        controlFlowFlattening: true,
        controlFlowFlatteningThreshold: 0.75,
        deadCodeInjection: true,
        deadCodeInjectionThreshold: 0.4,
        debugProtection: true,
        identifierNamesGenerator: 'hexadecimal',
        renameGlobals: false,
        selfDefending: true,
        simplify: true,
        splitStrings: true,
        splitStringsChunkLength: 10,
        stringArray: true,
        stringArrayCallsTransform: true,
        stringArrayCallsTransformThreshold: 0.5,
        stringArrayEncoding: ['base64'],
        stringArrayIndexShift: true,
        stringArrayRotate: true,
        stringArrayShuffle: true,
        stringArrayWrappersCount: 2,
        stringArrayWrappersChainedCalls: true,
        stringArrayWrappersParametersMaxCount: 4,
        stringArrayWrappersType: 'function',
        stringArrayThreshold: 0.75,
        transformObjectKeys: true,
        unicodeEscapeSequence: false
    });
    const outputPath = path.join(__dirname, file.replace('.js', '-obfuscated.js'));
    fs.writeFileSync(outputPath, result.getObfuscatedCode(), 'utf8');
    console.log(`✅ Ofuscado: ${file} -> ${outputPath}`);
});