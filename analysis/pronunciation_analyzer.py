"""
Advanced pronunciation analysis module with phoneme alignment and scoring
"""
import re
import numpy as np
from utils.logger import setup_logger

logger = setup_logger(__name__)

class PronunciationAnalyzer:
    def __init__(self):
        """
        Initialize the pronunciation analyzer with phoneme mappings
        """
        # Basic phoneme mappings for English sounds
        self.phoneme_map = {
            # Vowels
            'AA': ['a', 'o', 'ah'],
            'AE': ['a', 'e'],
            'AH': ['u', 'a'],
            'AO': ['o', 'au'],
            'AW': ['ou', 'ow'],
            'AY': ['i', 'y'],
            'EH': ['e', 'ai'],
            'ER': ['er', 'ur'],
            'EY': ['a', 'ei'],
            'IH': ['i', 'y'],
            'IY': ['ee', 'i'],
            'OW': ['o', 'oa'],
            'OY': ['oi', 'oy'],
            'UH': ['oo', 'u'],
            'UW': ['oo', 'u'],
            
            # Consonants
            'B': ['b'],
            'CH': ['ch', 'tch'],
            'D': ['d'],
            'DH': ['th'],
            'F': ['f'],
            'G': ['g'],
            'HH': ['h'],
            'JH': ['j', 'dg'],
            'K': ['k', 'c'],
            'L': ['l'],
            'M': ['m'],
            'N': ['n'],
            'NG': ['ng'],
            'P': ['p'],
            'R': ['r'],
            'S': ['s'],
            'SH': ['sh'],
            'T': ['t'],
            'TH': ['th'],
            'V': ['v'],
            'W': ['w'],
            'Y': ['y'],
            'Z': ['z'],
            'ZH': ['zh', 'si']
        }
        
        # Common phonetic errors and substitutions
        self.phonetic_errors = {
            'TH': ['D', 'T', 'F'],  # th often substituted with d, t, or f
            'R': ['W', 'L'],        # r often substituted with w or l
            'L': ['R', 'W'],        # l often substituted with r or w
            'V': ['B', 'F'],        # v often substituted with b or f
            'ZH': ['SH', 'S'],      # zh often substituted with sh or s
            'DH': ['D', 'T'],       # th (voiced) often substituted with d or t
        }

    def phoneme_align(self, transcription, original_text):
        """
        Perform basic phoneme-level alignment between transcription and original text
        :param transcription: Actual transcribed text
        :param original_text: Original prompt text
        :return: Alignment information
        """
        # Tokenize both texts
        transcribed_words = transcription.lower().split()
        original_words = original_text.lower().split()
        
        alignment_info = {
            'word_matches': [],
            'phoneme_errors': [],
            'accuracy_score': 0.0,
            'details': []
        }
        
        min_len = min(len(transcribed_words), len(original_words))
        
        for i in range(min_len):
            orig_word = self._preprocess_word(original_words[i])
            trans_word = self._preprocess_word(transcribed_words[i])
            
            # Calculate word similarity
            similarity = self._word_similarity(orig_word, trans_word)
            
            alignment_info['word_matches'].append({
                'original': original_words[i],
                'transcribed': transcribed_words[i],
                'similarity': similarity,
                'match': similarity > 0.7  # Threshold for considering a match
            })
            
            # Detect phoneme-level errors
            if similarity <= 0.7:
                phoneme_errors = self._detect_phoneme_errors(orig_word, trans_word)
                alignment_info['phoneme_errors'].extend(phoneme_errors)
                
                alignment_info['details'].append({
                    'position': i,
                    'original_word': original_words[i],
                    'transcribed_word': transcribed_words[i],
                    'errors': phoneme_errors
                })
        
        # Calculate overall accuracy
        correct_words = sum(1 for match in alignment_info['word_matches'] if match['match'])
        alignment_info['accuracy_score'] = correct_words / len(original_words) if original_words else 0
        
        return alignment_info

    def pronunciation_scoring(self, transcription, original_text, alignment_info=None):
        """
        Comprehensive pronunciation scoring
        :param transcription: Actual transcribed text
        :param original_text: Original prompt text
        :param alignment_info: Pre-computed alignment info (optional)
        :return: Pronunciation score dictionary
        """
        if alignment_info is None:
            alignment_info = self.phoneme_align(transcription, original_text)
        
        # Calculate pronunciation score based on multiple factors
        clarity_score = self._calculate_clarity_score(transcription, original_text)
        fluency_score = self._calculate_fluency_score(transcription)
        accuracy_score = alignment_info['accuracy_score'] * 10  # Scale to 0-10
        
        # Weighted combination of scores
        pronunciation_score = {
            'overall': round((clarity_score * 0.4 + fluency_score * 0.3 + accuracy_score * 0.3), 2),
            'clarity': round(clarity_score, 2),
            'fluency': round(fluency_score, 2),
            'accuracy': round(accuracy_score, 2),
            'alignment_details': alignment_info
        }
        
        return pronunciation_score

    def _preprocess_word(self, word):
        """
        Preprocess a word for phoneme analysis
        """
        # Remove punctuation and convert to lowercase
        word = re.sub(r'[^\w\s]', '', word.lower())
        return word

    def _word_similarity(self, word1, word2):
        """
        Calculate similarity between two words using edit distance
        """
        if not word1 and not word2:
            return 1.0
        if not word1 or not word2:
            return 0.0
        
        # Calculate edit distance
        distance = self._edit_distance(word1, word2)
        max_len = max(len(word1), len(word2))
        
        if max_len == 0:
            return 1.0
        
        similarity = 1 - (distance / max_len)
        return similarity

    def _edit_distance(self, s1, s2):
        """
        Calculate edit distance between two strings
        """
        if len(s1) < len(s2):
            return self._edit_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def _detect_phoneme_errors(self, original_word, transcribed_word):
        """
        Detect potential phoneme-level errors
        """
        errors = []
        
        # Compare character by character to detect substitutions
        min_len = min(len(original_word), len(transcribed_word))
        
        for i in range(min_len):
            orig_char = original_word[i]
            trans_char = transcribed_word[i]
            
            if orig_char != trans_char:
                errors.append({
                    'position': i,
                    'expected': orig_char,
                    'actual': trans_char,
                    'type': 'substitution'
                })
        
        # Check for missing or extra characters
        if len(original_word) > len(transcribed_word):
            for i in range(len(transcribed_word), len(original_word)):
                errors.append({
                    'position': i,
                    'expected': original_word[i],
                    'actual': None,
                    'type': 'deletion'
                })
        elif len(transcribed_word) > len(original_word):
            for i in range(len(original_word), len(transcribed_word)):
                errors.append({
                    'position': i,
                    'expected': None,
                    'actual': transcribed_word[i],
                    'type': 'insertion'
                })
        
        return errors

    def _calculate_clarity_score(self, transcription, original_text):
        """
        Calculate clarity score based on pronunciation accuracy
        """
        # Count number of words that were correctly transcribed
        transcribed_words = set(transcription.lower().split())
        original_words = set(original_text.lower().split())
        
        if not original_words:
            return 0.0
        
        # Calculate intersection over union for word overlap
        intersection = len(transcribed_words.intersection(original_words))
        union = len(transcribed_words.union(original_words))
        
        if union == 0:
            return 0.0
        
        # Also consider word order and position
        transcribed_list = transcription.lower().split()
        original_list = original_text.lower().split()
        
        positional_matches = 0
        for i in range(min(len(transcribed_list), len(original_list))):
            if transcribed_list[i] == original_list[i]:
                positional_matches += 1
        
        positional_score = positional_matches / len(original_list) if original_list else 0.0
        
        # Combine word overlap and positional accuracy
        clarity_score = (intersection / len(original_words) * 0.6) + (positional_score * 0.4)
        
        # Scale to 0-10 range
        return min(10.0, clarity_score * 10)

    def _calculate_fluency_score(self, transcription):
        """
        Calculate fluency score based on speech flow and continuity
        """
        words = transcription.split()
        
        if not words:
            return 0.0
        
        # Count repetitions (potential disfluencies)
        unique_words = set(words)
        repetition_ratio = 1 - (len(unique_words) / len(words)) if words else 0
        
        # Count common fillers
        fillers = ['um', 'uh', 'er', 'like', 'so', 'well', 'you know', 'actually', 'basically']
        filler_count = sum(1 for word in words if word.lower() in fillers)
        filler_ratio = filler_count / len(words)
        
        # Calculate fluency score (lower repetition and filler count = higher score)
        repetition_penalty = min(3, repetition_ratio * 10)  # Max 3 point penalty
        filler_penalty = min(2, filler_ratio * 8)  # Max 2 point penalty
        
        # Base score is 10, subtract penalties
        fluency_score = max(0, 10 - repetition_penalty - filler_penalty)
        
        return fluency_score

    def generate_pronunciation_report(self, transcription, original_text):
        """
        Generate a comprehensive pronunciation report
        """
        alignment_info = self.phoneme_align(transcription, original_text)
        scoring = self.pronunciation_scoring(transcription, original_text, alignment_info)
        
        report = {
            'summary': {
                'overall_score': scoring['overall'],
                'clarity_score': scoring['clarity'],
                'fluency_score': scoring['fluency'],
                'accuracy_score': scoring['accuracy']
            },
            'alignment_details': alignment_info,
            'recommendations': self._generate_recommendations(scoring, alignment_info)
        }
        
        return report

    def _generate_recommendations(self, scoring, alignment_info):
        """
        Generate recommendations based on pronunciation analysis
        """
        recommendations = []
        
        if scoring['clarity'] < 6:
            recommendations.append("Focus on clearer pronunciation of individual words.")
        
        if scoring['fluency'] < 6:
            recommendations.append("Work on reducing fillers and speech hesitations.")
        
        if scoring['accuracy'] < 6:
            recommendations.append("Practice matching the original text more closely.")
        
        if alignment_info['phoneme_errors']:
            recommendations.append(f"Address {len(alignment_info['phoneme_errors'])} phoneme-level errors detected.")
        
        if not recommendations:
            recommendations.append("Pronunciation looks good! Keep practicing to maintain your skills.")
        
        return recommendations