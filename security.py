"""
Security Module - AES encryption/decryption and message handling
"""

import os
import json
import base64
import time
from typing import Dict, Optional, Tuple
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes


class AESCrypto:
    """AES-256 encryption/decryption for secure message transmission"""
    
    def __init__(self, key: bytes = None):
        """Initialize with a 256-bit key or generate new one"""
        self.key = key or get_random_bytes(32)  # 256 bits
        self.block_size = AES.block_size
        
    def encrypt(self, plaintext: str) -> Tuple[bytes, bytes]:
        """
        Encrypt plaintext using AES-256-CBC.
        Returns (ciphertext, iv)
        """
        iv = get_random_bytes(self.block_size)
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        padded_data = pad(plaintext.encode('utf-8'), self.block_size)
        ciphertext = cipher.encrypt(padded_data)
        return ciphertext, iv
    
    def decrypt(self, ciphertext: bytes, iv: bytes) -> str:
        """Decrypt ciphertext using AES-256-CBC"""
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(ciphertext), self.block_size)
        return decrypted.decode('utf-8')
    
    def encrypt_base64(self, plaintext: str) -> Dict[str, str]:
        """Encrypt and return base64 encoded result"""
        ciphertext, iv = self.encrypt(plaintext)
        return {
            "ciphertext": base64.b64encode(ciphertext).decode('utf-8'),
            "iv": base64.b64encode(iv).decode('utf-8')
        }
    
    def decrypt_base64(self, encrypted_data: Dict[str, str]) -> str:
        """Decrypt from base64 encoded data"""
        ciphertext = base64.b64decode(encrypted_data["ciphertext"])
        iv = base64.b64decode(encrypted_data["iv"])
        return self.decrypt(ciphertext, iv)


class SecureMessage:
    """Represents a secure message in the UAV swarm network"""
    
    def __init__(self, sender_id: int, receiver_id: str, payload: str,
                 message_id: str = None, is_dummy: bool = False):
        self.message_id = message_id or f"MSG-{int(time.time() * 1000)}-{sender_id}"
        self.sender_id = sender_id
        self.receiver_id = receiver_id
        self.payload = payload
        self.is_dummy = is_dummy
        self.timestamp = time.time()
        self.hop_count = 0
        self.relay_path: list = []
        self.encryption_layers = 0
        self.encrypted_content: Optional[Dict] = None
        
    def to_dict(self) -> Dict:
        """Convert message to dictionary for serialization"""
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "is_dummy": self.is_dummy,
            "timestamp": self.timestamp,
            "hop_count": self.hop_count,
            "relay_path": self.relay_path.copy(),
            "encryption_layers": self.encryption_layers,
            "encrypted_content": self.encrypted_content
        }
    
    def add_relay_hop(self, relay_id: int):
        """Record a relay hop in the message path"""
        self.relay_path.append(relay_id)
        self.hop_count += 1


class MessageEncryptor:
    """Handles layered encryption for onion-style routing"""
    
    def __init__(self):
        self.layer_keys: Dict[int, AESCrypto] = {}
        self._initialize_layer_keys(max_layers=5)
        
    def _initialize_layer_keys(self, max_layers: int):
        """Pre-generate encryption keys for each layer"""
        for i in range(max_layers):
            self.layer_keys[i] = AESCrypto()
            
    def encrypt_message(self, message: SecureMessage, layers: int) -> SecureMessage:
        """Apply multiple encryption layers to a message"""
        content = json.dumps({
            "payload": message.payload,
            "sender_id": message.sender_id,
            "timestamp": message.timestamp
        })
        
        # Apply encryption layers
        for layer in range(layers):
            crypto = self.layer_keys[layer]
            encrypted = crypto.encrypt_base64(content)
            content = json.dumps(encrypted)
            
        message.encrypted_content = json.loads(content)
        message.encryption_layers = layers
        return message
    
    def decrypt_layer(self, message: SecureMessage, current_layer: int) -> SecureMessage:
        """Decrypt one layer of encryption (simulated re-encryption at relay)"""
        if current_layer > 0:
            crypto = self.layer_keys[current_layer - 1]
            content = json.dumps(message.encrypted_content)
            try:
                decrypted = crypto.decrypt_base64(json.loads(content))
                message.encrypted_content = json.loads(decrypted)
            except Exception:
                pass  # Simulation - actual decryption may fail
        return message
    
    def re_encrypt(self, message: SecureMessage) -> SecureMessage:
        """
        Simulate re-encryption at relay node.
        In real implementation, this would change the encryption key.
        """
        # Simulate re-encryption overhead without actually changing content
        if message.encrypted_content:
            # Add a re-encryption marker
            message.encrypted_content["re_encrypted"] = True
        return message


class SecurityManager:
    """Manages all security operations for the swarm"""
    
    def __init__(self):
        self.encryptor = MessageEncryptor()
        self.message_log: list = []
        
    def create_secure_message(self, sender_id: int, receiver_id: str, 
                               payload: str, encryption_rounds: int,
                               is_dummy: bool = False) -> SecureMessage:
        """Create and encrypt a secure message"""
        message = SecureMessage(sender_id, receiver_id, payload, is_dummy=is_dummy)
        message = self.encryptor.encrypt_message(message, encryption_rounds)
        self.message_log.append(message.to_dict())
        return message
    
    def process_at_relay(self, message: SecureMessage, relay_id: int) -> SecureMessage:
        """Process message at relay node (re-encrypt and forward)"""
        message.add_relay_hop(relay_id)
        message = self.encryptor.re_encrypt(message)
        return message
    
    def create_dummy_message(self, sender_id: int) -> SecureMessage:
        """Create a dummy message for traffic obfuscation"""
        dummy_payload = base64.b64encode(get_random_bytes(32)).decode('utf-8')
        return self.create_secure_message(
            sender_id=sender_id,
            receiver_id="DUMMY",
            payload=dummy_payload,
            encryption_rounds=1,
            is_dummy=True
        )
    
    def get_message_stats(self) -> Dict:
        """Get statistics on processed messages"""
        total = len(self.message_log)
        dummy_count = sum(1 for m in self.message_log if m.get("is_dummy", False))
        return {
            "total_messages": total,
            "real_messages": total - dummy_count,
            "dummy_messages": dummy_count,
            "dummy_ratio": dummy_count / total if total > 0 else 0
        }
