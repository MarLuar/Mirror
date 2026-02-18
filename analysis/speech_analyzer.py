import re
import numpy as np
from utils.logger import setup_logger
from analysis.pronunciation_analyzer import PronunciationAnalyzer

logger = setup_logger(__name__)

class SpeechAnalyzer:
    def __init__(self):
        """
        Initialize the speech analyzer
        """
        # Initialize the pronunciation analyzer
        self.pronunciation_analyzer = PronunciationAnalyzer()

        # Define grammar rules and patterns
        self.grammar_rules = {
            'subject_verb_agreement': [r'\bi am\b', r'\byou are\b', r'\bhe is\b', r'\bshe is\b'],
            'article_usage': [r'\ba \w+[aeiou]', r'\ban \w+[bcdfgjklmnpqrstvwxz]'],  # Basic a/an rules
            'common_errors': [r'\bthe the\b', r'\band and\b'],  # Double words
        }

        # Define vocabulary complexity indicators
        self.advanced_vocabulary = [
            'sophisticated', 'elaborate', 'comprehensive', 'articulate',
            'eloquent', 'persuasive', 'coherent', 'concise', 'precise',
            'nuanced', 'subtle', 'intricate', 'complex', 'detailed',
            'thorough', 'exhaustive', 'meticulous', 'rigorous', 'methodical'
        ]

        # Define positive indicators for speech quality
        self.positive_indicators = [
            'because', 'however', 'therefore', 'additionally', 'furthermore',
            'nevertheless', 'consequently', 'meanwhile', 'otherwise', 'finally'
        ]

    def analyze_speech(self, transcription, original_prompt=None):
        """
        Analyze different aspects of the speech
        :param transcription: Transcribed text
        :param original_prompt: Original text that was supposed to be read
        :return: Dictionary with scores for different aspects
        """
        if not transcription:
            return {
                'pronunciation': 0,
                'articulation': 0,
                'pace': 0,
                'clarity': 0,
                'emotion': 'neutral'
            }

        analysis_results = {}

        # Analyze pronunciation (based on transcription quality and comparison to prompt)
        if original_prompt:
            # Use advanced pronunciation analysis when original prompt is available
            pronunciation_report = self.pronunciation_analyzer.generate_pronunciation_report(
                transcription, original_prompt
            )
            # Use the overall pronunciation score
            analysis_results['pronunciation'] = pronunciation_report['summary']['overall_score']
        else:
            # Use basic estimation when no original prompt is available
            analysis_results['pronunciation'] = self._estimate_pronunciation(transcription, original_prompt)

        # Analyze articulation (word formation and clarity)
        analysis_results['articulation'] = self._analyze_articulation(transcription, original_prompt)

        # Analyze pace (rhythm and timing)
        analysis_results['pace'] = self._analyze_pace(transcription, original_prompt)

        # Analyze clarity (how clear the speech was)
        analysis_results['clarity'] = self._analyze_clarity(transcription, original_prompt)

        # Analyze emotion in the speech
        analysis_results['emotion'] = self._analyze_emotion(transcription)

        return analysis_results

    def _analyze_fluency(self, text):
        """
        Analyze speech fluency based on repetitions, fillers, and flow
        """
        words = text.lower().split()

        if len(words) == 0:
            return 0

        # Count repeated words (potential disfluencies)
        repeated_word_count = 0
        for i in range(len(words) - 1):
            if words[i] == words[i+1]:
                repeated_word_count += 1

        # Count common filler words
        filler_words = ['um', 'uh', 'er', 'like', 'so', 'well', 'you know', 'actually', 'basically', 'literally', 'right', 'okay', 'kind of']
        filler_count = sum(1 for word in words if word in filler_words)

        # Calculate fluency score (lower repetition and filler count = higher score)
        total_words = len(words)

        # Calculate ratios
        repetition_ratio = repeated_word_count / total_words if total_words > 0 else 0
        filler_ratio = filler_count / total_words if total_words > 0 else 0

        # Calculate penalties (higher penalties for more disfluencies)
        # Use more sensitive penalties that will affect the score more significantly
        repetition_penalty = repetition_ratio * 20  # More sensitive to repetitions
        filler_penalty = filler_ratio * 15  # More sensitive to fillers

        # Base score is 10, subtract penalties
        fluency_score = max(0, 10 - repetition_penalty - filler_penalty)

        # Adjust for very short speeches which might seem artificially fluent
        if total_words < 5:
            fluency_score *= 0.7  # Reduce score for very short speeches

        return round(fluency_score, 2)

    def _analyze_emotion(self, text):
        """
        Analyze the emotional tone of the speech
        """
        if not text:
            return 'neutral'

        text_lower = text.lower()
        words = text_lower.split()

        # Emotion word dictionaries
        emotion_keywords = {
            'joy': [
                'happy', 'excited', 'wonderful', 'amazing', 'fantastic', 'great',
                'love', 'pleased', 'delighted', 'thrilled', 'glad', 'cheerful',
                'joy', 'celebrate', 'success', 'perfect', 'awesome', 'brilliant'
            ],
            'sadness': [
                'sad', 'unhappy', 'depressed', 'terrible', 'awful', 'horrible',
                'disappointed', 'frustrated', 'regret', 'sorry', 'miserable',
                'heartbroken', 'lonely', 'gloomy', 'pessimistic', 'tragic'
            ],
            'anger': [
                'angry', 'mad', 'furious', 'annoyed', 'irritated', 'frustrated',
                'hate', 'disgusted', 'rage', 'hostile', 'aggressive', 'offended',
                'resentment', 'bitter', 'infuriated', 'livid', 'enraged'
            ],
            'fear': [
                'scared', 'afraid', 'nervous', 'worried', 'anxious', 'frightened',
                'terrified', 'panicked', 'concerned', 'apprehensive', 'timid',
                'phobic', 'intimidated', 'uneasy', 'disturbed', 'alarmed'
            ],
            'surprise': [
                'surprised', 'amazed', 'shocked', 'stunned', 'astonished',
                'unbelievable', 'incredible', 'unexpected', 'remarkable', 'wow',
                'astounding', 'startling', 'unanticipated', 'flabbergasted'
            ],
            'disgust': [
                'disgusted', 'disgusting', 'gross', 'nauseous', 'revolted', 'sickened',
                'appalled', 'repulsed', 'horrified', 'icky', 'yucky', 'filthy',
                'contaminated', 'repugnant', 'loathsome', 'abhorrent'
            ]
        }

        # Count emotion keywords
        emotion_counts = {}
        for emotion, keywords in emotion_keywords.items():
            count = sum(1 for word in words if word in keywords)
            emotion_counts[emotion] = count

        # Determine dominant emotion based on keyword counts
        dominant_emotion = max(emotion_counts, key=emotion_counts.get)

        # If no emotion keywords found, default to neutral
        if emotion_counts[dominant_emotion] == 0:
            # Additional check: look for sentiment-bearing expressions
            positive_indicators = [
                'good', 'nice', 'excellent', 'fine', 'okay', 'alright', 'super',
                'cool', 'awesome', 'brilliant', 'outstanding', 'marvelous'
            ]
            negative_indicators = [
                'bad', 'terrible', 'awful', 'poor', 'wrong', 'incorrect', 'badly',
                'horrible', 'dreadful', 'atrocious', 'inferior', 'unsatisfactory'
            ]

            pos_count = sum(1 for word in words if word in positive_indicators)
            neg_count = sum(1 for word in words if word in negative_indicators)

            if pos_count > neg_count:
                return 'positive'
            elif neg_count > pos_count:
                return 'negative'
            else:
                return 'neutral'

        return dominant_emotion

    def _analyze_grammar(self, text):
        """
        Analyze grammar based on predefined rules
        Note: Since the user is reading provided text, grammar reflects transcription accuracy
        rather than the user's grammar skills
        """
        score = 5  # Base score

        # Check for common transcription errors that might indicate poor grammar
        error_patterns = [r'\bthe the\b', r'\band and\b', r'\bit it\b']
        for pattern in error_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            score -= len(matches) * 2  # Penalty for repeated words (likely transcription errors)

        # Additional checks for transcription quality
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        # Count incomplete sentences (no ending punctuation)
        words = text.split()
        if words and not re.search(r'[.!?]\s*$', text):
            score -= 1  # Minor penalty for incomplete final sentence

        # Normalize score to 0-10 range
        score = max(0, min(10, score))

        return round(score, 2)

    def _analyze_vocabulary(self, text):
        """
        Analyze vocabulary as it appears in the transcription
        Note: Since the user is reading provided text, this reflects transcription accuracy
        rather than the user's vocabulary skills
        """
        text_lower = text.lower()
        words = text_lower.split()

        if not words:
            return 0

        # Since user is reading provided text, evaluate how well complex words were pronounced/transcribed
        # Count how many words from the advanced vocabulary list appear correctly in the transcription
        advanced_count = sum(1 for word in self.advanced_vocabulary if word in text_lower)

        # Calculate how many of the expected words were transcribed correctly
        total_advanced_in_text = sum(1 for word in self.advanced_vocabulary if word in text_lower)

        # Base score on transcription accuracy of complex words
        if len(words) == 0:
            return 0

        # Calculate ratio of advanced vocabulary that was successfully transcribed
        vocab_score = (advanced_count / len(words)) * 20 if len(words) > 0 else 0
        vocab_score = min(10, vocab_score)  # Cap at 10

        return round(vocab_score, 2)

    def _analyze_clarity(self, text, original_prompt=None):
        """
        Analyze clarity based on sentence structure and coherence
        """
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return 0

        # If we have the original prompt, compare the structure and content
        if original_prompt:
            # Use a more forgiving comparison that accounts for natural variations when reading
            from difflib import SequenceMatcher

            # Calculate similarity ratio between original and transcription
            similarity = SequenceMatcher(None, original_prompt.lower(), text.lower()).ratio()

            # Calculate how much of the original was attempted
            original_word_count = len(original_prompt.split())
            transcription_word_count = len(text.split())
            attempt_ratio = min(1.0, transcription_word_count / original_word_count) if original_word_count > 0 else 1.0

            # Use a more forgiving approach that rewards partial completion with good accuracy
            # Weight similarity higher than completion to reward accurate reading
            clarity_score = (similarity * 0.7 + attempt_ratio * 0.3) * 10

            # Ensure minimum score for reasonable attempts
            if attempt_ratio > 0.5 and similarity > 0.4:  # At least half the text with 40% similarity
                clarity_score = max(clarity_score, 5.0)

            return round(clarity_score, 2)
        else:
            # Fallback to previous method if no original prompt
            word_counts = []
            for sentence in sentences:
                words = sentence.split()
                if words:  # Only count non-empty sentences
                    word_counts.append(len(words))

            if not word_counts:
                return 0

            avg_length = np.mean(word_counts)

            # Score based on sentence length (not too short, not too long)
            # Ideal range is 8-15 words per sentence
            if 8 <= avg_length <= 15:
                clarity_score = 8  # Lower base score to make it more realistic
            elif avg_length < 8:
                clarity_score = max(0, 8 - (8 - avg_length) * 1.0)  # Reduced penalty
            else:  # Too long
                clarity_score = max(0, 8 - (avg_length - 15) * 0.5)  # Reduced penalty

            # Adjust for number of sentences (more sentences can indicate better structure)
            # But cap the bonus to prevent artificially high scores
            if len(sentences) >= 2:
                clarity_score = min(10, clarity_score + 1.5)  # Reduced bonus
            elif len(sentences) == 1:
                clarity_score = max(0, clarity_score - 1)  # Slight penalty for single sentence

        return round(clarity_score, 2)

    def _analyze_confidence(self, text):
        """
        Analyze confidence based on use of definitive language
        """
        text_lower = text.lower()
        words = text_lower.split()

        if not words:
            return 0

        # Positive indicators of confidence
        confident_expressions = [
            'clearly', 'obviously', 'definitely', 'certainly', 'absolutely',
            'without doubt', 'undoubtedly', 'indeed', 'surely', 'indeed',
            'obvious', 'certain', 'absolut', 'exact', 'precise', 'confident'
        ]

        # Negative indicators of uncertainty
        uncertain_expressions = [
            'maybe', 'perhaps', 'possibly', 'might', 'could', 'should',
            'i think', 'i believe', 'i guess', 'sort of', 'kind of',
            'maybe', 'probabl', 'seem', 'appear', 'tend to', 'somewhat'
        ]

        # Count positive and negative indicators
        positive_count = sum(1 for word in words if any(expr in word for expr in confident_expressions))
        negative_count = sum(1 for word in words if any(expr in word for expr in uncertain_expressions))

        # Also consider sentence structure - questions often indicate uncertainty
        question_count = text.count('?')
        question_ratio = question_count / len(text.split('.')) if '.' in text else 0

        # Calculate base score based on word count (longer speech might indicate more confidence)
        length_factor = min(2, len(words) / 20)  # Up to 2 points for longer speeches

        # Adjust based on positive/negative indicators
        confidence_score = 3 + length_factor + (positive_count * 1.0) - (negative_count * 1.5) - (question_ratio * 2)

        # Normalize to 0-10 range
        confidence_score = max(0, min(10, confidence_score))

        return round(confidence_score, 2)

    def _analyze_articulation(self, text, original_prompt=None):
        """
        Analyze articulation based on word formation and clarity
        """
        words = text.split()

        if not words:
            return 0

        # If we have the original prompt, compare the transcription to it for articulation
        if original_prompt:
            # Use a more forgiving comparison that accounts for natural variations when reading
            from difflib import SequenceMatcher

            # Calculate similarity ratio between original and transcription
            similarity = SequenceMatcher(None, original_prompt.lower(), text.lower()).ratio()

            # Calculate how much of the original was attempted
            original_word_count = len(original_prompt.split())
            transcription_word_count = len(text.split())
            attempt_ratio = min(1.0, transcription_word_count / original_word_count) if original_word_count > 0 else 1.0

            # Use a more forgiving approach that rewards partial completion with good accuracy
            # Weight similarity higher than completion to reward accurate reading
            articulation_score = (similarity * 0.8 + attempt_ratio * 0.2) * 10

            # Ensure minimum score for reasonable attempts
            if attempt_ratio > 0.5 and similarity > 0.4:  # At least half the text with 40% similarity
                articulation_score = max(articulation_score, 5.0)

            return round(articulation_score, 2)
        else:
            # Fallback to previous method if no original prompt
            # Count very short or potentially unclear words that might indicate poor articulation
            # This is a proxy measure since we don't have audio
            unclear_indicators = ['uh', 'um', 'ah', 'er', 'hm', 'hmm']
            unclear_count = sum(1 for word in words if word.lower() in unclear_indicators)

            # Calculate ratio of unclear indicators
            unclear_ratio = unclear_count / len(words)

            # Also consider word length as a proxy for articulation
            # Very short words might indicate mumbled or poorly articulated speech
            short_word_count = sum(1 for word in words if len(word) <= 2 and word.lower() not in ['i', 'a', 'to', 'of', 'in', 'on', 'at', 'or', 'be', 'an'])
            short_word_ratio = short_word_count / len(words)

            # Base score of 10, subtract points based on unclear and short word ratios
            articulation_score = max(0, 10 - (unclear_ratio * 30) - (short_word_ratio * 5))

            return round(articulation_score, 2)

    def _analyze_pace(self, text, original_prompt=None):
        """
        Analyze speaking pace based on pauses and rhythm
        """
        import re

        # If we have the original prompt, compare the transcription to it for pace
        if original_prompt:
            # Use a more forgiving approach that considers how much of the text was read
            # rather than focusing on sentence structure
            from difflib import SequenceMatcher

            # Calculate similarity ratio between original and transcription
            similarity = SequenceMatcher(None, original_prompt.lower(), text.lower()).ratio()

            # Calculate how much of the original was attempted
            original_word_count = len(original_prompt.split())
            transcription_word_count = len(text.split())
            attempt_ratio = min(1.0, transcription_word_count / original_word_count) if original_word_count > 0 else 1.0

            # For pace, focus on how much was read and how accurately
            # Reward both completion and accuracy
            pace_score = (attempt_ratio * 0.6 + similarity * 0.4) * 10

            # Ensure minimum score for reasonable attempts
            if attempt_ratio > 0.3:  # At least 30% of the text
                pace_score = max(pace_score, 4.0)

            return round(pace_score, 2)
        else:
            # Fallback to previous method if no original prompt
            # Split by sentence endings to estimate natural pauses
            sentences = re.split(r'[.!?]+', text)
            sentences = [s.strip() for s in sentences if s.strip()]

            if not sentences:
                return 0

            # Count words per sentence to estimate pace consistency
            word_counts = []
            for sentence in sentences:
                words = sentence.split()
                if words:
                    word_counts.append(len(words))

            if not word_counts:
                return 0

            # Calculate standard deviation as a measure of pace consistency
            import numpy as np
            std_dev = np.std(word_counts) if len(word_counts) > 1 else 0

            # Lower std deviation = more consistent pace = higher score
            # Base score of 7, subtract points for inconsistency
            pace_score = max(0, 7 - (std_dev * 0.3))

            return round(pace_score, 2)

    def _estimate_pronunciation(self, text, original_prompt=None):
        """
        Estimate pronunciation quality based on transcription accuracy
        (Note: True pronunciation assessment requires audio analysis)
        """
        words = text.split()

        # If we have the original prompt, compare the transcription to it
        if original_prompt:
            from difflib import SequenceMatcher

            # Calculate similarity ratio between original and transcription
            similarity = SequenceMatcher(None, original_prompt.lower(), text.lower()).ratio()

            # Calculate how much of the original was attempted
            original_word_count = len(original_prompt.split())
            transcription_word_count = len(text.split())
            attempt_ratio = min(1.0, transcription_word_count / original_word_count) if original_word_count > 0 else 1.0

            # Use a more forgiving approach that rewards partial completion with good accuracy
            # Weight similarity higher than completion to reward accurate reading
            pronunciation_score = (similarity * 0.7 + attempt_ratio * 0.3) * 10

            # Ensure minimum score for reasonable attempts
            if attempt_ratio > 0.5 and similarity > 0.4:  # At least half the text with 40% similarity
                pronunciation_score = max(pronunciation_score, 5.0)

            return round(min(10, pronunciation_score), 2)
        else:
            # Fallback if no original prompt provided
            if len(words) < 3:
                return 2  # Lower score for very short transcriptions
            elif len(words) < 5:
                return 4  # Low-medium score for short transcriptions
            elif len(words) < 10:
                return 6  # Medium score for medium transcriptions
            else:
                # Higher score for longer, more complete transcriptions
                # assuming that clear pronunciation leads to better transcription
                return min(9, 6 + (len(words) - 10) * 0.3)  # Cap at 9 to prevent max score