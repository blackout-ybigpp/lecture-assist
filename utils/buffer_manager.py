class BufferManager:
    def __init__(self):
        self.buffer = []

    def add_data(self, data):
        """버퍼에 데이터를 추가"""
        self.buffer.append(data)

    def get_all_data(self):
        """버퍼에 저장된 모든 데이터를 문자열로 반환"""
        return " ".join(self.buffer)

    def clear(self):
        """버퍼를 초기화"""
        self.buffer = []

# 싱글톤 객체 생성
buffer_manager = BufferManager()
