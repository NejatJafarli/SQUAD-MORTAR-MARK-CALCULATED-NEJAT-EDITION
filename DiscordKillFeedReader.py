import discord
import json
import re
from collections import defaultdict

class KillTracker:
    def __init__(self, token, channel_id, your_name):
        """
        Kill Feed Tracker - Sadece yeni kill'leri topla
        
        Args:
            token: Discord user token
            channel_id: Kill feed kanal ID
            your_name: Senin oyundaki tam ismin
        """
        self.token = token
        self.channel_id = channel_id
        self.your_name = your_name.strip()
        
        # İstatistikler
        self.stats = {
            'your_kills': 0,
            'your_deaths': 0,
            'your_victims': [],  # [{name, weapon, time}, ...]
            'your_killers': []   # [{name, weapon, time}, ...]
        }
        
        # Discord client
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        
        @self.client.event
        async def on_ready():
            print('='*60)
            print('🎮 KILL TRACKER BAŞLATILDI')
            print('='*60)
            print(f'✓ Bağlandı: {self.client.user}')
            print(f'✓ Takip edilen: {self.your_name}')
            print(f'✓ Kanal ID: {self.channel_id}')
            print('='*60)
            print('\n⏳ Yeni kill\'ler bekleniyor...\n')
        
        @self.client.event
        async def on_message(message):
            # Sadece kill feed kanalından
            if message.channel.id == self.channel_id:
                await self.process_kill(message.content)
    
    def parse_kill_message(self, text):
        """
        Kill mesajını parse et
        
        Format: `Killer` vurdu `Victim` `Weapon` ile | HH:MM:SS
        """
        text = text.strip()
        
        # Pattern 1: Normal kill
        pattern1 = r'`([^`]+)`\s+vurdu\s+`([^`]+)`\s+`([^`]+)`\s+ile\s+\|\s+(\d{2}:\d{2}:\d{2})'
        
        # Pattern 2: Teamkill
        pattern2 = r'`([^`]+)`\s+takım arkadaşını vurdu\s+`([^`]+)`\s+`([^`]+)`\s+ile\s+\|\s+(\d{2}:\d{2}:\d{2})'
        
        match = re.search(pattern2, text)
        if match:
            return {
                'killer': match.group(1).strip(),
                'victim': match.group(2).strip(),
                'weapon': match.group(3).strip(),
                'time': match.group(4).strip(),
                'is_teamkill': True
            }
        
        match = re.search(pattern1, text)
        if match:
            return {
                'killer': match.group(1).strip(),
                'victim': match.group(2).strip(),
                'weapon': match.group(3).strip(),
                'time': match.group(4).strip(),
                'is_teamkill': False
            }
        
        return None
    
    async def process_kill(self, message_text):
        """
        Kill mesajını işle
        """
        kill_data = self.parse_kill_message(message_text)
        
        if not kill_data:
            return
        
        killer = kill_data['killer']
        victim = kill_data['victim']
        weapon = kill_data['weapon']
        time = kill_data['time']
        is_tk = kill_data['is_teamkill']
        
        # Sen öldürdüysen
        if killer == self.your_name:
            self.stats['your_kills'] += 1
            self.stats['your_victims'].append({
                'name': victim,
                'weapon': weapon,
                'time': time,
                'teamkill': is_tk
            })
            
            print(f"\n{'='*60}")
            print(f"🎯 KILL #{self.stats['your_kills']}")
            print(f"{'='*60}")
            print(f"   Kurban: {victim}")
            print(f"   Silah: {weapon}")
            print(f"   Zaman: {time}")
            if is_tk:
                print(f"   ⚠️ TEAMKILL!")
            print(f"{'='*60}")
            
            self.print_current_stats()
            self.save_stats()
        
        # Sen öldürüldüysen
        elif victim == self.your_name:
            self.stats['your_deaths'] += 1
            self.stats['your_killers'].append({
                'name': killer,
                'weapon': weapon,
                'time': time,
                'teamkill': is_tk
            })
            
            print(f"\n{'='*60}")
            print(f"💀 DEATH #{self.stats['your_deaths']}")
            print(f"{'='*60}")
            print(f"   Öldüren: {killer}")
            print(f"   Silah: {weapon}")
            print(f"   Zaman: {time}")
            if is_tk:
                print(f"   ⚠️ TEAMKILL!")
            print(f"{'='*60}")
            
            self.print_current_stats()
            self.save_stats()
    
    def print_current_stats(self):
        """
        Güncel istatistikleri yazdır
        """
        print(f"\n📊 GÜNCEL İSTATİSTİKLER")
        print(f"   🎯 Kill: {self.stats['your_kills']}")
        print(f"   💀 Death: {self.stats['your_deaths']}")
        
        if self.stats['your_kills'] > 0 and self.stats['your_deaths'] > 0:
            kd = self.stats['your_kills'] / self.stats['your_deaths']
            print(f"   📈 K/D: {kd:.2f}")
        elif self.stats['your_kills'] > 0:
            print(f"   📈 K/D: {self.stats['your_kills']:.2f} (0 death)")
    
    def print_full_summary(self):
        """
        Detaylı özet
        """
        print("\n" + "="*60)
        print(f"📊 DETAYLI İSTATİSTİKLER - {self.your_name}")
        print("="*60)
        print(f"🎯 Toplam Kill: {self.stats['your_kills']}")
        print(f"💀 Toplam Death: {self.stats['your_deaths']}")
        
        if self.stats['your_kills'] > 0 and self.stats['your_deaths'] > 0:
            kd = self.stats['your_kills'] / self.stats['your_deaths']
            print(f"📈 K/D Oranı: {kd:.2f}")
        
        # En çok öldürdüklerin
        if self.stats['your_victims']:
            victim_counts = defaultdict(int)
            for v in self.stats['your_victims']:
                victim_counts[v['name']] += 1
            
            print(f"\n🎯 EN ÇOK ÖLDÜRDÜKLERİN:")
            for name, count in sorted(victim_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   {name}: {count}x")
        
        # Seni en çok öldürenler
        if self.stats['your_killers']:
            killer_counts = defaultdict(int)
            for k in self.stats['your_killers']:
                killer_counts[k['name']] += 1
            
            print(f"\n💀 SENİ EN ÇOK ÖLDÜRENLER:")
            for name, count in sorted(killer_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   {name}: {count}x")
        
        # En çok kullandığın silahlar
        if self.stats['your_victims']:
            weapon_counts = defaultdict(int)
            for v in self.stats['your_victims']:
                weapon_counts[v['weapon']] += 1
            
            print(f"\n🔫 EN ÇOK KULLANDIĞIN SİLAHLAR:")
            for weapon, count in sorted(weapon_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   {weapon}: {count}x")
        
        # Tüm kill'lerin listesi
        if self.stats['your_victims']:
            print(f"\n📜 TÜM KILL'LERİN:")
            for i, v in enumerate(self.stats['your_victims'], 1):
                tk = " [TK]" if v['teamkill'] else ""
                print(f"   {i}. {v['name']} - {v['weapon']} - {v['time']}{tk}")
        
        # Tüm death'lerin listesi
        if self.stats['your_killers']:
            print(f"\n☠️ TÜM DEATH'LERİN:")
            for i, k in enumerate(self.stats['your_killers'], 1):
                tk = " [TK]" if k['teamkill'] else ""
                print(f"   {i}. {k['name']} - {k['weapon']} - {k['time']}{tk}")
        
        print("="*60)
    
    def save_stats(self):
        """
        İstatistikleri JSON'a kaydet
        """
        filename = f"kill_stats_{self.your_name.replace(' ', '_')}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
    
    def run(self):
        """
        Tracker'ı başlat
        """
        self.client.run(self.token)


# =====================================================
# KULLANIM
# =====================================================

if __name__ == "__main__":
    
    # ========================
    # BİLGİLERİNİ BURAYA YAZ
    # ========================
    
    TOKEN = "MFA.XXXXXXXXXXXXXXXXXXXXXXXXX"  # Discord token
    CHANNEL_ID = 1261266124276764763          # Kill feed kanal ID
    YOUR_NAME = "GM RJT"                      # Oyundaki TAM ismin
    
    # Tracker oluştur
    tracker = KillTracker(TOKEN, CHANNEL_ID, YOUR_NAME)
    
    # Çalıştır (Ctrl+C ile durdur)
    try:
        tracker.run()
    except KeyboardInterrupt:
        print("\n\n" + "="*60)
        print("⏸️  TRACKER DURDURULDU")
        print("="*60)
        tracker.print_full_summary()
        print("\n💾 İstatistikler kaydedildi!")
        print("="*60)