#coding : UTF-8

import hashlib
import json
import requests
from textwrap import dedent
from time import time
from uuid import uuid4
from urllib.parse import urlparse

from flask import Flask, jsonify, request

class Blockchain(object):
    def __init__(self):
        self.chain = []
        self.currentTrunsactions = []

        self.nodes=set()

        #ジェネシスブロックを作る
        self.new_block(proof=100,previous_hash=1)

    def new_block(self,proof,previous_hash=None):
        """
        新しいブロックチェーンを作り、チェーンに加える
        
        :param proof: <int> プルーフ・オブ・ワークから得られるプルーフ
        :param previous_hash: (オプション)<str> 前のブロックからのハッシュ
        :return: <dict> 新しいブロック
        """
        
        block = {
            'index' : len(self.chain) - 1,
            'time_stamp' : time(),
            'transaction' : self.currentTrunsactions,
            'proof' : proof,
            'previous_hash' : previous_hash or self.hash(self.chain[-1]),
        }

        #現在のトランザクションリストをリセット
        self.currentTrunsactions=[]

        self.chain.append(block)
        return block

    def new_transaction(self,sender,recipient,amount):
        """
        新しいトランザクションをリストに加える
        
        次に発掘されるブロックに加える新しいトランザクションを作る
        :param sender: <str> 送信者のアドレス
        :param recipient: <str> 受信者のアドレス
        :param amount: <int> 量
        :return: <int> このトランザクションを含めたブロックのアドレス
        """

        self.currentTrunsactions.append({
            "sender":sender,
            "recipient":recipient,
            "amount":amount,
        })
        return self.last_block["index"]+1

    def register_node(self,address):
        """
        ノードリストに新しいノードを加える
        :param address: <str> ノードのアドレス　例："http://http://192.168.0.5:5000"
        :return: None
        """

        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    def valid_chain(self,chain):
        """
        ブロックチェーンが正しいかを確認する

        :param chain: <list>　ブロックチェーン
        :return: <bool> Trueだと正しく、Falseだと不正
        """
        last_block = chain[0]
        curren_index = 1

        while curren_index < len(chain):
            block = chain[curren_index]

            print(f'{last_block}')
            print(f'{block}')
            print("\n----------------------\n")

            #ブロックのハッシュが正しいかを確認
            if block['previous_hash'] != self.hash(last_block):
                return False

            #プルーフ・オブ・ワークが正しいか
            if self.valid_proof(last_block['proof'],block['proof']) :
                return False
            
            last_block=block
            curren_index+=1

        return True

    def resolve_conflicts(self):
        """
        ネットワーク上の最も長いチェーンの最も長いチェーンで自らのチェーンを置き換える
        :return: <bool> 置き換えられた際にTrue,そうでなければfalse
        """

        neighbours = self.nodes
        new_chain = None

        #自らのチェーンの長さでとりあえず初期化
        max_length = len(self.chain)
        
        #他のすべてのチェーンを調べる
        for node  in neighbours :
            response = requests.get(f'http://{node}/chain')

            if response.status_code == 200 :
                length = response.json()['length']
                chain = response.json()['chain']

                #そのチェーンがより長いか、そしてチェーン自体が有効かを確認
                if length > max_length and self.valid_chain(chain) :
                    max_length = length
                    new_chain = chain
        
        #自分のチェーンより長いものがあればそれで更新
        if new_chain :
            self.chain = new_chain
            return True
        
        return False 

    @staticmethod
    def hash(block):
        """
        ブロックをハッシュ化する
        
        ブロックのSHA-256ハッシュを作る
        :param block: <dick> ブロック
        :return: <str> ハッシュ値
        """
        #ディクショナリがソートされてるものとし、ハッシュの一貫性を保つ
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        #チェーンの最後のブロックを返す
        return self.chain[-1]

    def proof_of_work(self,last_proof):
        """
        シンプルなプルーフ・オブ・ワークの説明-
        - hash(p'p)の最初の４つが0となるようなpを探す
        - p'は前のブロックのプルーフ値　pは新しいブロックのプルーフ
        :param last_proof: <int> 前のブロックのプルーフ
        :return: <int>
        """

        proof = 0
        while self.valid_proof(last_proof,proof) is False:
            proof+=1
            
        return proof

    @staticmethod
    def valid_proof(last_proof,proof):
        """
        プルーフが正しいか確認する:hash(last_proof,proof)の上位4つが０になっているか
        :param last_proof: <int> 前のプルーフ
        :param proof: <int> 現在のプルーフ
        :return: <bool> 正しければTrue、そうでなければFalse
        """
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()
        return guess_hash[:4] == "0000"

#ノードを作る
app = Flask(__name__)

#このノードのグローバルにユニークなアドレスを作る
node_indetifire = str(uuid4()).replace('-','')

#ブロックチェーンクラスをインスタンス化　
blockchain = Blockchain()

# メソッドはPOSTで、/transactions/newエンドポイントを作る。メソッドはPOSTなのでデータを送信する
@app.route ('/transactions/new',methods=['POST'])
def new_transaction():
    values = request.get_json()


    #POSTされたデータに必要なデータがあるか
    required = ['sender', 'recipient', 'amount']
    if not all(k in values for k in required):
        return 'Missing values', 400
    
    #新しいトランザクションを作る
    index = blockchain.new_transaction(values['sender'],values['recipient'],values['amount'])
    response = {'message' : f'トランザクションはブロック{index}に追加されました'}
    return jsonify(response),201

# メソッドはGETで、/mineエンドポイントを作る
@app.route('/mine',methods=['GET'])
def mine():
    #次のプルーフを見つけるためプルーフ・オブ・ワークアルゴリズムを使用する
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    #プルーフを発掘したことに対する報酬を得る
    #送信者の欄は発掘者が新しいコインを発掘したことを表すために"0"とする
    blockchain.new_transaction(
        sender="0",
        recipient=node_indetifire,
        amount=1,
    )

    #チェーンに新しいブロックを加えることで、新しいブロックを採掘する
    block = blockchain.new_block(proof)

    response = {
        'message' : '新しいブロックを採掘しました',
        'index' : block['index'],
        'transactions' : block['transaction'],
        'proof' : block['proof'],
        'previous_hash' : block['previous_hash'],
    }
    return jsonify(response),200

# メソッドはGETで、フルのブロックチェーンをリターンする/chainエンドポイントを作る
@app.route('/chain',methods=['GET'])
def full_chain():
    response = {
        'chain' : blockchain.chain,
        'length': len(blockchain.chain)
    }
    return jsonify(response), 200

# port5000でサーバを起動する
if __name__=='__main__':
    app.run(host='localhost',port=5000)
