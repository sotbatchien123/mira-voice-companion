/**
 * Nhép miệng theo nguyên âm tiếng Việt: chữ của đoạn đang đọc -> khẩu hình từng âm tiết (aa/ih/ou/ee/oh, có sẵn
 * trong model VRoid), và bắt nhịp âm tiết từ âm lượng audio thật để biết lúc nào chuyển sang âm tiết kế.
 */

// Nguyên âm sau khi bỏ dấu thanh: ă/â đọc mở như a, ê như e, ô/ơ như o, ư như u, y như i
const VOWEL_BASE = { a: "a", ă: "a", â: "a", e: "e", ê: "e", i: "i", y: "i", o: "o", ô: "o", ơ: "o", u: "u", ư: "u" };
const VISEME = { a: "aa", e: "ee", i: "ih", o: "oh", u: "ou" };
export const VISEMES = ["aa", "ih", "ou", "ee", "oh"];

// Dấu thanh: huyền, sắc, ngã, hỏi, nặng. Giữ lại dấu mũ/trăng/móc vì chúng đổi nguyên âm (â, ă, ơ...)
const TONE_MARKS = /[̣̀́̃̉]/g;

function stripTone(syllable) {
  return syllable.toLowerCase().normalize("NFD").replace(TONE_MARKS, "").normalize("NFC");
}

/** Nguyên âm chính của một âm tiết (đã bỏ dấu thanh), hoặc null nếu không có. */
export function mainVowel(syllable) {
  let s = stripTone(syllable);
  // "qu", "gi" + nguyên âm: u/i chỉ là phụ âm đầu ("quá" -> a, "già" -> a), nhưng "gì" vẫn là i
  if (s.startsWith("qu")) s = s.slice(2);
  else if (s.startsWith("gi") && [...s.slice(2)].some((c) => c in VOWEL_BASE)) s = s.slice(2);
  const vowels = [...s].filter((c) => c in VOWEL_BASE);
  if (!vowels.length) return null;
  const [first, second] = vowels;
  // Âm đệm o/u đứng trước nguyên âm chính: "hoa" -> a, "khỏe" -> e, "tuần" -> â, "thuyền" -> ê
  if (first === "o" && second && "aăe".includes(second)) return second;
  if (first === "u" && second && "yêâơ".includes(second)) {
    return vowels.includes("ê") ? "ê" : second;
  }
  // Nguyên âm đôi iê/yê: âm chính là ê ("yêu", "tiền", "biết")
  if ("iy".includes(first) && second === "ê") return "ê";
  return first;
}

/** Danh sách khẩu hình, mỗi âm tiết một cái: "Chào anh!" -> ["aa", "aa"]. */
export function syllableVisemes(text) {
  return (text.match(/\p{L}+/gu) ?? []).map((syl) => {
    const v = mainVowel(syl);
    return v ? VISEME[VOWEL_BASE[v]] : "aa";
  });
}

/**
 * Bắt nhịp âm tiết từ âm lượng: mỗi lần âm lượng (so với đỉnh gần đây) tụt xuống rồi vọt lên lại là một âm tiết mới.
 * Ngưỡng chỉnh theo giọng VieNeu thật (xem specs/005-lively-avatar/tasks.md).
 */
export class SyllableTracker {
  constructor({ low = 0.35, high = 0.55, minGap = 0.09 } = {}) {
    this.low = low;
    this.high = high;
    this.minGap = minGap; // tối đa ~11 âm tiết/giây
    this.reset();
  }

  reset() {
    this.peak = 0.05;
    this.armed = true; // đang chờ âm tiết mới
    this.sinceOnset = 1;
  }

  /** @returns {boolean} true nếu khung này là đầu một âm tiết mới */
  update(level, dt) {
    this.sinceOnset += dt;
    this.peak = Math.max(level, this.peak - 0.05 * dt, 0.02);
    const norm = level / this.peak;
    if (norm < this.low) this.armed = true;
    if (this.armed && norm > this.high && this.sinceOnset >= this.minGap) {
      this.armed = false;
      this.sinceOnset = 0;
      return true;
    }
    return false;
  }
}
