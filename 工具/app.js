/* 選項內容的字典 */
let optionDict = {
  san2: {
    filename: "kaodata.dat",
    width: 64,
    height: 80,
    count: -1,
    halfHeight: true,
  },
  san3: {
    filename: "kaodata.dat",
    width: 64,
    height: 80,
    count: -1,
    halfHeight: false,
  },
  kohryuki: {
    filename: "kao.kr1",
    width: 64,
    height: 80,
    count: -1,
    halfHeight: false,
  },
  suikoden: {
    filename: "kaoibm.dat",
    width: 64,
    height: 80,
    count: -1,
    halfHeight: false,
  },
};

let faceParameters;

document.addEventListener("DOMContentLoaded", function () {
  const fileInput = document.getElementById("fileInput");
  const canvas = document.getElementById("canvas");

  fileInput.addEventListener("change", (event) => {
    const file = event.target.files[0];
    const reader = new FileReader();

    reader.readAsArrayBuffer(file);

    reader.onload = (event) => {
      const arrayBuffer = event.target.result;
      const uint8Buffer = new Uint8Array(arrayBuffer);
      let width = faceParameters.width;
      let height = faceParameters.height;
      let num_col = 16;

      var faceDataSize = faceParameters.halfHeight
        ? (width * height * 3) / 8 / 2
        : (width * height * 3) / 8;

      var faceCount =
        faceParameters.count === -1
          ? Math.floor(uint8Buffer.byteLength / faceDataSize)
          : faceParameters.count;

      canvas.width = width * num_col;
      canvas.height = height * Math.ceil(faceCount / num_col);

      const ctx = canvas.getContext("2d");
      for (let i = 0; i < faceCount; i++) {
        var pos = i * faceDataSize;
        var posX = (i % num_col) * width;
        var posY = Math.floor(i / num_col) * height;
        var faceData = uint8Buffer.slice(pos, pos + faceDataSize);
        faceImage = dataToImage(
          faceData,
          width,
          height,
          faceParameters.halfHeight
        );
        ctx.putImageData(faceImage, posX, posY);
      }
    };
  });
});

function dataToImage(data, width, height, halfHeight) {
  var selectBox = document.getElementById("selectOption");
  var hh = optionDict[selectBox.value].halfHeight;

  const imageData = new ImageData(width, height);
  var colorIndexes = toColorIndexes(data);

  var colors = [
    [0, 0, 0],
    [85, 255, 85],
    [255, 85, 85],
    [255, 255, 85],
    [85, 85, 255],
    [85, 255, 255],
    [255, 85, 255],
    [255, 255, 255],
  ];

  for (i = 0; i < colorIndexes.length; i++) {
    let x = i % width;
    let y = Math.floor(i / width);
    var c = colors[colorIndexes[i]];
    if (hh) {
      let idx = (2 * y * width + x) * 4;
      imageData.data[idx] = c[0];
      imageData.data[idx + 1] = c[1];
      imageData.data[idx + 2] = c[2];
      imageData.data[idx + 3] = 255;
      idx = ((2 * y + 1) * width + x) * 4;
      imageData.data[idx] = c[0];
      imageData.data[idx + 1] = c[1];
      imageData.data[idx + 2] = c[2];
      imageData.data[idx + 3] = 255;
    } else {
      let idx = (y * width + x) * 4;
      imageData.data[idx] = c[0];
      imageData.data[idx + 1] = c[1];
      imageData.data[idx + 2] = c[2];
      imageData.data[idx + 3] = 255;
    }
  }
  return imageData;
}

function toColorIndexes(data) {
  var groups = grouper(data, 3);

  var indexes = [];
  groups.forEach(function (element) {
    for (i = 7; i >= 0; --i) {
      n =
        (((element[0] >> i) & 1) << 2) |
        (((element[1] >> i) & 1) << 1) |
        ((element[2] >> i) & 1);
      indexes.push(n);
    }
  });

  return indexes;
}

function grouper(arr, size, fillValue = null) {
  const groups = [];
  for (let i = 0; i < arr.length; i += size) {
    groups.push(arr.slice(i, i + size));
  }
  if (fillValue !== null && groups.length * size < arr.length) {
    const fillLength = size - (arr.length % size);
    const fillArr = new Array(fillLength).fill(fillValue);
    groups.push([...arr.slice(groups.length * size), ...fillArr]);
  }
  return groups;
}

/* 檢查按鈕狀態 */
function checkButtonStatus() {
  var selectBox = document.getElementById("selectOption");
  var fileInput = document.getElementById("fileInput");
  var downloadButton = document.getElementById("downloadButton");
  var selectedOption = document.getElementById("selectedOption");

  if (selectBox.value !== "" && fileInput.value !== "") {
    // 如果選項和檔案都已選，就啟用下載按鈕
    downloadButton.disabled = false;
  } else {
    // 否則就禁用下載按鈕
    downloadButton.disabled = true;
  }
  if (selectBox.value !== "") {
    // 如果選項已選，就啟用檔案上傳按鈕
    fileInput.disabled = false;
    faceParameters = optionDict[selectBox.value];
    selectedOption.innerText = faceParameters.filename;
  } else {
    // 否則就禁用檔案上傳按鈕
    fileInput.disabled = true;
    selectedOption.innerText = "";
  }
}

/* 下載檔案 */
function downloadFile() {
  alert("Downloading file...");
}
